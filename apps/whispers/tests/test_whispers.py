from unittest import mock

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.memberships.models import Membership, SealTier
from apps.whispers.models import Broadcast, Whisper
from apps.whispers.services import whisper_service


@pytest.mark.django_db
def test_inbox_shows_messages_and_marks_them_read(client, make_member):
    member = make_member()
    whisper_service.send(member, "Hello", "Welcome to the club")
    client.force_login(member)

    first = client.get(reverse("whispers:inbox")).content.decode()
    assert "Welcome to the club" in first
    assert "is-unread" in first

    second = client.get(reverse("whispers:inbox")).content.decode()
    assert "is-unread" not in second
    assert not Whisper.objects.filter(is_read=False).exists()


@pytest.mark.django_db
def test_members_only_see_their_own(client, make_member):
    me, other = make_member(), make_member()
    whisper_service.send(other, "Secret for other")
    client.force_login(me)

    assert "Secret for other" not in client.get(reverse("whispers:inbox")).content.decode()


@pytest.mark.django_db
def test_bell_badge_shows_unread_count(client, make_member):
    member = make_member()
    whisper_service.send(member, "One")
    whisper_service.send(member, "Two")
    client.force_login(member)

    html = client.get(reverse("core:portal")).content.decode()

    assert '<span class="whisper-badge">2</span>' in html


@pytest.mark.django_db
def test_public_pages_run_no_badge_queries(client, django_assert_num_queries):
    with django_assert_num_queries(0):
        client.get(reverse("core:welcome"))


@pytest.mark.django_db(transaction=True)
def test_broadcast_reaches_audience_once(make_member, manager_user, seal_tiers):
    active = [make_member() for _ in range(3)]
    make_member(status="pending")
    make_member(status="suspended")

    broadcast = whisper_service.create_broadcast("Tonight", "Live music at 9", Broadcast.Audience.ALL, manager_user)

    assert Whisper.objects.filter(broadcast=broadcast).count() == 3
    assert set(Whisper.objects.values_list("member_id", flat=True)) == {m.pk for m in active}
    broadcast.refresh_from_db()
    assert broadcast.recipients == 3

    # Retrying the fan-out must not duplicate messages.
    whisper_service.fan_out(broadcast.pk)
    assert Whisper.objects.filter(broadcast=broadcast).count() == 3


@pytest.mark.django_db(transaction=True)
def test_broadcast_to_paid_holders_only(make_member, manager_user, seal_tiers):
    paid, free = make_member(), make_member()
    gold = SealTier.objects.get(code="gold")
    now = timezone.now()
    Membership.objects.create(
        member=paid, tier=gold, starts_at=now, ends_at=now + timezone.timedelta(days=30), source="staff"
    )

    whisper_service.create_broadcast("VIP", "Gold night", Broadcast.Audience.PAID, manager_user)

    assert list(Whisper.objects.values_list("member_id", flat=True)) == [paid.pk]
    assert not Whisper.objects.filter(member=free).exists()


@pytest.mark.django_db
def test_broadcast_page_is_manager_only(client, staff_user, manager_user):
    client.force_login(staff_user)
    assert client.get(reverse("dashboard:broadcasts")).status_code == 403

    client.force_login(manager_user)
    assert client.get(reverse("dashboard:broadcasts")).status_code == 200


@pytest.mark.django_db(transaction=True)
def test_redemption_and_payment_send_whispers(make_member, seal_tiers):
    from apps.keys.models import KeysEntry
    from apps.keys.services import ledger_service
    from apps.treasures.models import Treasure
    from apps.treasures.services import redemption_service

    member = make_member()
    ledger_service.post_entry(member, 5, KeysEntry.Reason.ADMIN_ADJUST, note="seed")
    treasure = Treasure.objects.create(name="Cigar", keys_cost=2)
    with mock.patch("apps.notifications.tasks.telegram"):
        redemption = redemption_service.redeem(member, treasure.pk)

    whisper = Whisper.objects.get(member=member, kind="treasure")
    assert redemption.claim_code in whisper.body
