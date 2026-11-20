"""
Unlocking treasures with keys, handing them over, and cancelling.

Locking order is always Treasure row, then KeysAccount row (inside
ledger_service). A single fixed order prevents deadlocks between requests.
"""

import secrets

from django.db import IntegrityError, transaction
from django.db.models import F
from django.utils import timezone
from django.utils.translation import gettext as _

from apps.keys.models import KeysEntry
from apps.keys.services import ledger_service
from apps.keys.services.ledger_service import InsufficientKeys

from ..models import Redemption, Treasure

CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


class RedemptionError(Exception):
    """User-safe message."""


def _new_code():
    return "".join(secrets.choice(CODE_ALPHABET) for _ in range(6))


def redeem(member, treasure_id: int) -> Redemption:
    """Spend keys on a treasure. All or nothing."""
    from apps.notifications.tasks import notify_redemption

    with transaction.atomic():
        treasure = Treasure.objects.select_for_update().filter(pk=treasure_id, is_active=True).first()
        if treasure is None:
            raise RedemptionError(_("This treasure is no longer available."))
        if not treasure.in_stock:
            raise RedemptionError(_("This treasure is out of stock."))

        redemption = _create_redemption(member, treasure)
        try:
            ledger_service.post_entry(
                member,
                -treasure.keys_cost,
                KeysEntry.Reason.REDEEM,
                reference=f"redemption:{redemption.pk}",
                note=treasure.name,
            )
        except InsufficientKeys as exc:
            raise RedemptionError(str(exc)) from None

        if treasure.stock is not None:
            Treasure.objects.filter(pk=treasure.pk).update(stock=F("stock") - 1)
        transaction.on_commit(lambda: notify_redemption.delay(redemption.pk))
    return redemption


def _create_redemption(member, treasure) -> Redemption:
    for _attempt in range(5):
        try:
            with transaction.atomic():
                return Redemption.objects.create(
                    member=member, treasure=treasure, keys_spent=treasure.keys_cost, claim_code=_new_code()
                )
        except IntegrityError:
            continue
    raise RuntimeError("Could not allocate a unique claim code")


def hand_over(redemption: Redemption, staff) -> Redemption:
    with transaction.atomic():
        redemption = Redemption.objects.select_for_update().get(pk=redemption.pk)
        if redemption.status != Redemption.Status.READY:
            raise RedemptionError(_("This treasure has already been handled."))
        redemption.status = Redemption.Status.HANDED_OVER
        redemption.handled_by = staff
        redemption.handled_at = timezone.now()
        redemption.save(update_fields=["status", "handled_by", "handled_at"])
    return redemption


def cancel(redemption: Redemption, staff) -> Redemption:
    """Staff cancel an uncollected treasure: refund the keys and restock."""
    with transaction.atomic():
        treasure = Treasure.objects.select_for_update().get(pk=redemption.treasure_id)
        redemption = Redemption.objects.select_for_update().get(pk=redemption.pk)
        if redemption.status != Redemption.Status.READY:
            raise RedemptionError(_("Only uncollected treasures can be cancelled."))
        redemption.status = Redemption.Status.CANCELLED
        redemption.handled_by = staff
        redemption.handled_at = timezone.now()
        redemption.save(update_fields=["status", "handled_by", "handled_at"])
        ledger_service.post_entry(
            redemption.member,
            redemption.keys_spent,
            KeysEntry.Reason.REDEEM_REFUND,
            reference=f"redemption:{redemption.pk}",
            note=treasure.name,
            created_by=staff,
        )
        if treasure.stock is not None:
            Treasure.objects.filter(pk=treasure.pk).update(stock=F("stock") + 1)
    return redemption
