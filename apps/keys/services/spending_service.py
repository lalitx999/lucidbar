"""Club spending recorded by staff, and the keys it earns."""

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils.translation import gettext as _

from apps.audit.services import audit_service
from apps.whispers.services import whisper_service

from ..models import KeysEntry, Spending
from . import ledger_service


class SpendingError(Exception):
    """User-safe message."""


def keys_for(amount_satang: int) -> int:
    per_key = settings.SPENDING_THB_PER_KEY * 100
    return amount_satang // per_key if per_key else 0


def record(member, amount_satang: int, staff, *, nonce, note: str = "") -> tuple[Spending, bool]:
    """Returns (spending, created). A repeated nonce returns the first record."""
    if amount_satang <= 0:
        raise SpendingError(_("Enter the amount of the bill."))
    if amount_satang > settings.SPENDING_MAX_THB * 100:
        raise SpendingError(_("That amount looks too large. Please check it."))
    if not member.is_verified or member.is_staff:
        raise SpendingError(_("This membership is not active."))
    keys = keys_for(amount_satang)
    with transaction.atomic():
        try:
            with transaction.atomic():
                spending = Spending.objects.create(
                    member=member,
                    amount_satang=amount_satang,
                    keys_awarded=keys,
                    note=note.strip()[:120],
                    nonce=nonce,
                    recorded_by=staff,
                )
        except IntegrityError:
            return Spending.objects.get(nonce=nonce), False
        if keys:
            ledger_service.post_entry(
                member,
                keys,
                KeysEntry.Reason.SPENDING,
                reference=f"spending:{spending.pk}",
                note=f"{amount_satang / 100:,.0f} THB",
                created_by=staff,
            )
            whisper_service.send(
                member,
                _("%(keys)d keys earned") % {"keys": keys},
                _("Thank you for spending %(amount)s THB at Lucid tonight.")
                % {"amount": f"{amount_satang / 100:,.0f}"},
            )
        audit_service.record(staff, "keys.spending", member, amount_thb=amount_satang / 100, keys=keys)
    return spending, True
