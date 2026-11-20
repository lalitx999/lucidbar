"""
The only way to change a key balance.

post_entry() locks the member's KeysAccount row (SELECT ... FOR UPDATE), so
concurrent requests are processed one after another. The new balance is
checked in Python for a friendly error and enforced again by a database
constraint, so a negative balance is impossible even if code has a bug.
"""

from django.db import IntegrityError, transaction
from django.utils.translation import gettext as _

from ..models import KeysAccount, KeysEntry


class InsufficientKeys(Exception):
    """User-safe message."""


def _locked_account(member) -> KeysAccount:
    # get_or_create first (it may insert), then take the row lock.
    KeysAccount.objects.get_or_create(member=member)
    return KeysAccount.objects.select_for_update().get(member=member)


def post_entry(member, delta: int, reason: str, *, reference: str = "", note: str = "", created_by=None) -> KeysEntry:
    """
    Add (positive delta) or remove (negative delta) keys.

    With a reference, the call is idempotent: posting the same reason and
    reference again returns the existing entry instead of a second one.
    Raises InsufficientKeys if the balance would go below zero.
    """
    if delta == 0:
        raise ValueError("delta must not be zero")

    with transaction.atomic():
        account = _locked_account(member)
        if reference:
            existing = KeysEntry.objects.filter(reason=reason, reference=reference).first()
            if existing:
                return existing

        new_balance = account.balance + delta
        if new_balance < 0:
            raise InsufficientKeys(
                _("Not enough keys. You need %(need)d more.") % {"need": -new_balance},
            )

        try:
            with transaction.atomic():
                entry = KeysEntry.objects.create(
                    account=account,
                    delta=delta,
                    balance_after=new_balance,
                    reason=reason,
                    reference=reference,
                    note=note[:255],
                    created_by=created_by,
                )
        except IntegrityError:
            # Same reference posted by a parallel transaction that committed first.
            if reference:
                return KeysEntry.objects.get(reason=reason, reference=reference)
            raise
        account.balance = new_balance
        account.save(update_fields=["balance", "updated_at"])
        return entry


def admin_adjust(member, delta: int, note: str, staff) -> KeysEntry:
    """Manual correction by a manager. A reason note is required."""
    if not note.strip():
        raise ValueError("An adjustment needs a note")
    return post_entry(member, delta, KeysEntry.Reason.ADMIN_ADJUST, note=note, created_by=staff)
