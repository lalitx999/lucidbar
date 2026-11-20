import threading
from unittest import mock

import pytest
from django.db import connection
from django.urls import reverse

from apps.keys.models import KeysEntry
from apps.keys.selectors import keys_selector
from apps.keys.services import ledger_service
from apps.treasures.models import Redemption, Treasure
from apps.treasures.services import redemption_service

R = KeysEntry.Reason
NOTIFY = "apps.notifications.tasks.telegram"


@pytest.fixture
def whisky(db):
    return Treasure.objects.create(name="Whisky", category="spirits", keys_cost=4, is_featured=True)


def fund(member, keys):
    ledger_service.post_entry(member, keys, R.ADMIN_ADJUST, note="test funding")


@pytest.mark.django_db(transaction=True)
def test_redeem_spends_keys_and_creates_claim(make_member, whisky):
    member = make_member()
    fund(member, 10)

    with mock.patch(NOTIFY) as tg:
        redemption = redemption_service.redeem(member, whisky.pk)

    assert redemption.status == Redemption.Status.READY
    assert len(redemption.claim_code) == 6
    assert keys_selector.balance_of(member) == 6
    assert KeysEntry.objects.get(reference=f"redemption:{redemption.pk}").delta == -4
    assert tg.send_message.called


@pytest.mark.django_db
def test_not_enough_keys_leaves_nothing_behind(make_member, whisky):
    member = make_member()
    fund(member, 3)

    with pytest.raises(redemption_service.RedemptionError, match="need 1 more"):
        redemption_service.redeem(member, whisky.pk)

    assert not Redemption.objects.exists()  # rolled back with the failed debit
    assert keys_selector.balance_of(member) == 3


@pytest.mark.django_db
def test_stock_is_decremented_and_enforced(make_member, whisky):
    whisky.stock = 1
    whisky.save()
    first, second = make_member(), make_member()
    fund(first, 10)
    fund(second, 10)

    redemption_service.redeem(first, whisky.pk)
    with pytest.raises(redemption_service.RedemptionError, match="out of stock"):
        redemption_service.redeem(second, whisky.pk)

    whisky.refresh_from_db()
    assert whisky.stock == 0
    assert keys_selector.balance_of(second) == 10


@pytest.mark.django_db
def test_inactive_treasure_cannot_be_redeemed(make_member, whisky):
    whisky.is_active = False
    whisky.save()
    member = make_member()
    fund(member, 10)

    with pytest.raises(redemption_service.RedemptionError, match="no longer available"):
        redemption_service.redeem(member, whisky.pk)


@pytest.mark.django_db
def test_cancel_refunds_once_and_restocks(make_member, staff_user, whisky):
    whisky.stock = 5
    whisky.save()
    member = make_member()
    fund(member, 10)
    redemption = redemption_service.redeem(member, whisky.pk)

    redemption_service.cancel(redemption, staff_user)
    with pytest.raises(redemption_service.RedemptionError):
        redemption_service.cancel(redemption, staff_user)

    assert keys_selector.balance_of(member) == 10
    whisky.refresh_from_db()
    assert whisky.stock == 5
    redemption.refresh_from_db()
    assert redemption.status == Redemption.Status.CANCELLED


@pytest.mark.django_db
def test_hand_over_only_once(make_member, staff_user, whisky):
    member = make_member()
    fund(member, 10)
    redemption = redemption_service.redeem(member, whisky.pk)

    redemption_service.hand_over(redemption, staff_user)
    with pytest.raises(redemption_service.RedemptionError):
        redemption_service.hand_over(redemption, staff_user)
    with pytest.raises(redemption_service.RedemptionError):
        redemption_service.cancel(redemption, staff_user)  # collected items are not refunded

    redemption.refresh_from_db()
    assert redemption.handled_by == staff_user


@pytest.mark.django_db(transaction=True)
def test_concurrent_redemptions_respect_stock_and_balance(make_member):
    """Eight members race for a treasure with stock 3: exactly 3 win."""
    treasure = Treasure.objects.create(name="Limited cap", keys_cost=2, stock=3)
    members = [make_member() for _ in range(8)]
    for m in members:
        fund(m, 5)

    barrier = threading.Barrier(len(members))
    outcomes = []
    lock = threading.Lock()

    def attempt(member):
        try:
            barrier.wait()
            with mock.patch(NOTIFY):
                redemption_service.redeem(member, treasure.pk)
            result = "ok"
        except redemption_service.RedemptionError:
            result = "refused"
        finally:
            connection.close()
        with lock:
            outcomes.append(result)

    threads = [threading.Thread(target=attempt, args=(m,)) for m in members]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    treasure.refresh_from_db()
    assert outcomes.count("ok") == 3
    assert treasure.stock == 0
    assert Redemption.objects.count() == 3
    assert sum(keys_selector.balance_of(m) for m in members) == 8 * 5 - 3 * 2


# ---------------------------------------------------------------------------
# Views
# ---------------------------------------------------------------------------
@pytest.mark.django_db(transaction=True)
def test_member_unlocks_from_detail_page(client, make_member, whisky):
    member = make_member()
    fund(member, 10)
    client.force_login(member)

    detail = client.get(reverse("treasures:detail", args=[whisky.pk])).content.decode()
    assert "Unlock for 4 keys" in detail

    with mock.patch(NOTIFY):
        response = client.post(reverse("treasures:unlock", args=[whisky.pk]), follow=True)

    code = Redemption.objects.get().claim_code
    assert code in response.content.decode()
    assert keys_selector.balance_of(member) == 6


@pytest.mark.django_db
def test_detail_shows_missing_keys(client, make_member, whisky):
    member = make_member()
    fund(member, 1)
    client.force_login(member)

    html = client.get(reverse("treasures:detail", args=[whisky.pk])).content.decode()

    assert "You need 3 more keys" in html
    assert "Unlock for" not in html


@pytest.mark.django_db
def test_unlock_requires_post(client, make_member, whisky):
    client.force_login(make_member())

    assert client.get(reverse("treasures:unlock", args=[whisky.pk])).status_code == 405


@pytest.mark.django_db
def test_catalog_lists_active_treasures(client, make_member, whisky, django_assert_max_num_queries):
    Treasure.objects.create(name="Hidden", keys_cost=1, is_active=False)
    client.force_login(make_member())

    with django_assert_max_num_queries(6):
        html = client.get(reverse("treasures:catalog")).content.decode()

    assert "Whisky" in html
    assert "Hidden" not in html


@pytest.mark.django_db
def test_keys_page_shows_balance_and_history(client, make_member):
    member = make_member()
    fund(member, 7)
    client.force_login(member)

    html = client.get(reverse("keys:keys")).content.decode()

    assert ">7<" in html
    assert "test funding" in html


def test_seed_command_is_idempotent(db):
    from django.core.management import call_command

    call_command("seed_demo_treasures", verbosity=0)
    call_command("seed_demo_treasures", verbosity=0)

    assert Treasure.objects.count() == 6
