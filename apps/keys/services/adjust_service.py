"""Manual key corrections by a manager, with an audit entry."""

from django.db import transaction
from django.utils.translation import gettext as _

from apps.audit.services import audit_service
from apps.whispers.services import whisper_service

from . import ledger_service


class AdjustError(Exception):
    """User-safe message."""


def adjust(member, delta: int, note: str, manager, *, tell_member: bool = True):
    note = note.strip()
    if delta == 0:
        raise AdjustError(_("Enter a number of keys other than zero."))
    if not note:
        raise AdjustError(_("Please write the reason for the adjustment."))
    with transaction.atomic():
        try:
            entry = ledger_service.admin_adjust(member, delta, note, manager)
        except ledger_service.InsufficientKeys as exc:
            raise AdjustError(str(exc)) from exc
        audit_service.record(manager, "keys.adjust", member, delta=delta, note=note, balance=entry.balance_after)
        if tell_member:
            title = _("%(n)d keys added") % {"n": delta} if delta > 0 else _("%(n)d keys removed") % {"n": -delta}
            whisper_service.send(member, title, note)
    return entry
