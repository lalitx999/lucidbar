"""Sending whispers to members' inboxes."""

from django.db import transaction
from django.utils import timezone

from apps.audit.services import audit_service

from ..models import Broadcast, Whisper

BATCH_SIZE = 500


def send(member, title: str, body: str = "", kind: str = Whisper.Kind.SYSTEM) -> Whisper:
    """Drop one message in a member's inbox. Cheap; safe inside other transactions."""
    return Whisper.objects.create(member=member, kind=kind, title=title[:120], body=body[:2000])


def mark_all_read(member) -> int:
    return Whisper.objects.filter(member=member, is_read=False).update(is_read=True)


def create_broadcast(title: str, body: str, audience: str, staff) -> Broadcast:
    """Record the broadcast and fan it out in the background."""
    from ..tasks import fan_out_broadcast

    with transaction.atomic():
        broadcast = Broadcast.objects.create(title=title, body=body, audience=audience, sent_by=staff)
        audit_service.record(staff, "broadcast.send", broadcast, audience=audience, title=title)
        transaction.on_commit(lambda: fan_out_broadcast.delay(broadcast.pk))
    return broadcast


def _audience_member_ids(audience: str):
    from apps.accounts.models import Member

    qs = Member.objects.filter(status=Member.Status.ACTIVE, is_staff=False)
    if audience == Broadcast.Audience.PAID:
        now = timezone.now()
        qs = qs.filter(
            memberships__tier__price_satang__gt=0,
            memberships__starts_at__lte=now,
            memberships__ends_at__gt=now,
        )
    return qs.values_list("pk", flat=True).distinct().order_by("pk").iterator()


def fan_out(broadcast_id: int) -> int:
    """
    Create one whisper per recipient with bulk inserts. Idempotent: members
    who already received this broadcast are skipped, so a retry is safe.
    """
    broadcast = Broadcast.objects.get(pk=broadcast_id)
    already = set(Whisper.objects.filter(broadcast=broadcast).values_list("member_id", flat=True))
    batch, total = [], 0
    for member_id in _audience_member_ids(broadcast.audience):
        if member_id in already:
            continue
        batch.append(
            Whisper(
                member_id=member_id,
                kind=Whisper.Kind.BROADCAST,
                title=broadcast.title,
                body=broadcast.body,
                broadcast=broadcast,
            )
        )
        if len(batch) >= BATCH_SIZE:
            Whisper.objects.bulk_create(batch)
            total += len(batch)
            batch = []
    if batch:
        Whisper.objects.bulk_create(batch)
        total += len(batch)
    Broadcast.objects.filter(pk=broadcast.pk).update(recipients=len(already) + total)
    return total
