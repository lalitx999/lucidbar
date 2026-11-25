"""Manager actions on member accounts. Each one is written to the audit log."""

from django.db import transaction
from django.utils.translation import gettext as _

from apps.audit.services import audit_service
from apps.whispers.services import whisper_service

from ..models import Member


class MemberAdminError(Exception):
    """User-safe message."""


def suspend(member: Member, actor, reason: str) -> Member:
    """Block sign-in. Existing sessions stop working on the next request."""
    reason = reason.strip()
    if not reason:
        raise MemberAdminError(_("Please write the reason for the suspension."))
    if member.is_staff or member.pk == actor.pk:
        raise MemberAdminError(_("Staff accounts cannot be suspended here."))
    with transaction.atomic():
        member = Member.objects.select_for_update().get(pk=member.pk)
        if member.status == Member.Status.SUSPENDED:
            raise MemberAdminError(_("This member is already suspended."))
        previous = member.status
        member.status = Member.Status.SUSPENDED
        member.save(update_fields=["status"])
        audit_service.record(actor, "member.suspend", member, reason=reason, previous=previous)
    return member


def reactivate(member: Member, actor) -> Member:
    with transaction.atomic():
        member = Member.objects.select_for_update().get(pk=member.pk)
        if member.status != Member.Status.SUSPENDED:
            raise MemberAdminError(_("This member is not suspended."))
        member.status = Member.Status.ACTIVE
        member.save(update_fields=["status"])
        audit_service.record(actor, "member.reactivate", member)
        whisper_service.send(member, _("Your membership is active again"), _("Welcome back to Lucid."))
    return member
