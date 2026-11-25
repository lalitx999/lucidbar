import threading

import pytest
from django.core import signing
from django.db import connection
from django.urls import reverse

from apps.checkin.models import CheckIn
from apps.checkin.services import card_service, checkin_service
from apps.keys.models import KeysAccount, KeysEntry
from apps.whispers.models import Whisper


def _balance(member):
    account = KeysAccount.objects.filter(member=member).first()
    return account.balance if account else 0


# ---------------------------------------------------------------------------
# The signed card
# ---------------------------------------------------------------------------
@pytest.mark.django_db
def test_card_token_round_trip(make_member):
    member = make_member()
    token = card_service.make_token(member)

    assert token.startswith("LUCID1.")
    assert card_service.read_token(token) == member.pk


@pytest.mark.django_db
def test_expired_card_is_refused(make_member, settings):
    token = card_service.make_token(make_member())
    settings.CHECKIN_CARD_MAX_AGE_SECONDS = -1

    with pytest.raises(card_service.CardError, match="expired"):
        card_service.read_token(token)


@pytest.mark.parametrize(
    "token",
    [
        "",
        "hello",
        "LUCID1.not-a-token",
        "LUCID1." + signing.dumps({"m": 1}, salt="some.other.salt"),
        "LUCID1." + signing.dumps({"m": "1"}, salt=card_service.SALT),
    ],
)
def test_forged_cards_are_refused(token):
    with pytest.raises(card_service.CardError, match="not a Lucid"):
        card_service.read_token(token)


@pytest.mark.django_db
def test_tampered_card_is_refused(make_member):
    token = card_service.make_token(make_member())
    tampered = token[:-2] + ("A" if token[-2] != "A" else "B") + token[-1]

    with pytest.raises(card_service.CardError):
        card_service.read_token(tampered)


# ---------------------------------------------------------------------------
# Checking in
# ---------------------------------------------------------------------------
@pytest.mark.django_db
def test_first_scan_awards_keys_second_does_not(make_member, staff_user, settings):
    settings.CHECKIN_KEYS = 5
    member = make_member()
    token = card_service.make_token(member)

    first = checkin_service.check_in_with_card(token, staff_user)
    second = checkin_service.check_in_with_card(token, staff_user)

    assert first.created and not second.created
    assert second.checkin.pk == first.checkin.pk
    assert _balance(member) == 5
    entry = KeysEntry.objects.get(account__member=member)
    assert entry.reason == KeysEntry.Reason.CHECKIN
    assert entry.created_by == staff_user
    assert Whisper.objects.filter(member=member, kind=Whisper.Kind.VISIT).count() == 1


@pytest.mark.django_db
def test_suspended_member_is_refused(make_member, staff_user):
    member = make_member(status="suspended")

    with pytest.raises(checkin_service.CheckInError, match="not active"):
        checkin_service.check_in_with_card(card_service.make_token(member), staff_user)
    assert not CheckIn.objects.exists()


@pytest.mark.django_db
def test_staff_account_card_is_refused(staff_user):
    with pytest.raises(checkin_service.CheckInError, match="not active"):
        checkin_service.check_in_with_card(card_service.make_token(staff_user), staff_user)


@pytest.mark.django_db(transaction=True)
def test_simultaneous_scans_award_keys_once(make_member, staff_user, settings):
    settings.CHECKIN_KEYS = 5
    member = make_member()
    token = card_service.make_token(member)
    barrier = threading.Barrier(5)
    created = []

    def attempt():
        try:
            barrier.wait()
            created.append(checkin_service.check_in_with_card(token, staff_user).created)
        finally:
            connection.close()

    threads = [threading.Thread(target=attempt) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert created.count(True) == 1 and len(created) == 5
    assert CheckIn.objects.count() == 1
    assert _balance(member) == 5


# ---------------------------------------------------------------------------
# Member pages
# ---------------------------------------------------------------------------
@pytest.mark.django_db
def test_card_qr_is_fresh_svg_for_signed_in_member(client, make_member):
    client.force_login(make_member())

    response = client.get(reverse("checkin:card_qr"))

    assert response["Content-Type"] == "image/svg+xml"
    assert "no-store" in response["Cache-Control"]
    assert response.content.startswith(b"<svg")


@pytest.mark.django_db
def test_card_qr_needs_login(client):
    assert client.get(reverse("checkin:card_qr")).status_code == 302


@pytest.mark.django_db
def test_identity_page_shows_card_and_visits(client, make_member, staff_user):
    member = make_member()
    checkin_service.check_in(member, staff_user)
    client.force_login(member)

    html = client.get(reverse("accounts:identity")).content.decode()

    assert reverse("checkin:card_qr") in html
    assert "Present at the door" in html
    assert "Visits" in html
