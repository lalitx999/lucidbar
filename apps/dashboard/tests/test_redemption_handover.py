from unittest import mock

import pytest
from django.urls import reverse

from apps.keys.models import KeysEntry
from apps.keys.selectors import keys_selector
from apps.keys.services import ledger_service
from apps.treasures.models import Redemption, Treasure
from apps.treasures.services import redemption_service

pytestmark = pytest.mark.django_db


@pytest.fixture
def redemption(make_member):
    member = make_member(full_name="Arthur Pendleton")
    ledger_service.post_entry(member, 10, KeysEntry.Reason.ADMIN_ADJUST, note="seed")
    treasure = Treasure.objects.create(name="Cigar", keys_cost=6)
    with mock.patch("apps.notifications.tasks.telegram"):
        return redemption_service.redeem(member, treasure.pk)


def test_requires_staff(client, make_member, redemption):
    client.force_login(make_member())

    assert client.get(reverse("dashboard:redemptions")).status_code == 403
    assert client.post(reverse("dashboard:redemption_hand_over", args=[redemption.pk])).status_code == 403


def test_search_by_claim_code(client, staff_user, redemption, django_assert_max_num_queries):
    client.force_login(staff_user)

    with django_assert_max_num_queries(5):
        html = client.get(reverse("dashboard:redemptions"), {"q": redemption.claim_code.lower()}).content.decode()

    assert "Arthur Pendleton" in html


def test_hand_over(client, staff_user, redemption):
    client.force_login(staff_user)

    client.post(reverse("dashboard:redemption_hand_over", args=[redemption.pk]))

    redemption.refresh_from_db()
    assert redemption.status == Redemption.Status.HANDED_OVER
    assert redemption.handled_by == staff_user


def test_cancel_refunds(client, staff_user, redemption):
    client.force_login(staff_user)

    client.post(reverse("dashboard:redemption_cancel", args=[redemption.pk]))

    assert keys_selector.balance_of(redemption.member) == 10
