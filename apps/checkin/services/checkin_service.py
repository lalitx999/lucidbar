"""
Door check-in. Staff scan the member's QR card; the first check-in of the
club night awards keys. A unique constraint on (member, night) makes a
second award impossible even when two scans arrive at the same moment.
"""

from dataclasses import dataclass

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils.translation import gettext as _

from apps.core.clock import business_night
from apps.keys.models import KeysEntry
from apps.keys.services import ledger_service
from apps.whispers.models import Whisper
from apps.whispers.services import whisper_service

from ..models import CheckIn
from . import card_service


class CheckInError(Exception):
    """User-safe message, shown to door staff."""


@dataclass(frozen=True)
class CheckInResult:
    checkin: CheckIn
    created: bool


def check_in_with_card(token: str, staff) -> CheckInResult:
    from apps.accounts.models import Member

    try:
        member_id = card_service.read_token(token)
    except card_service.CardError as exc:
        raise CheckInError(str(exc)) from exc
    member = Member.objects.filter(pk=member_id).first()
    if member is None or not member.is_active or member.is_staff:
        raise CheckInError(_("This membership is not active."))
    return check_in(member, staff)


def check_in(member, staff) -> CheckInResult:
    night = business_night()
    keys = settings.CHECKIN_KEYS
    with transaction.atomic():
        try:
            with transaction.atomic():
                checkin = CheckIn.objects.create(member=member, night=night, keys_awarded=keys, created_by=staff)
        except IntegrityError:
            existing = CheckIn.objects.select_related("member", "created_by").get(member=member, night=night)
            return CheckInResult(existing, created=False)
        if keys:
            ledger_service.post_entry(
                member, keys, KeysEntry.Reason.CHECKIN, reference=f"checkin:{checkin.pk}", created_by=staff
            )
        whisper_service.send(
            member,
            _("Welcome to Lucid"),
            _("Your visit tonight is recorded. %(keys)d keys added.") % {"keys": keys}
            if keys
            else _("Your visit tonight is recorded."),
            kind=Whisper.Kind.VISIT,
        )
    return CheckInResult(checkin, created=True)
