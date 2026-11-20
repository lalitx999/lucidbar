import threading

import pytest
from django.db import IntegrityError, connection, transaction

from apps.keys.models import KeysAccount, KeysEntry
from apps.keys.selectors import keys_selector
from apps.keys.services import ledger_service
from apps.keys.services.ledger_service import InsufficientKeys

R = KeysEntry.Reason


@pytest.mark.django_db
def test_credit_and_debit_update_balance_and_history(make_member):
    member = make_member()

    ledger_service.post_entry(member, 10, R.SIGNUP_BONUS)
    entry = ledger_service.post_entry(member, -4, R.REDEEM)

    assert keys_selector.balance_of(member) == 6
    assert entry.balance_after == 6
    assert list(keys_selector.history(member).values_list("delta", flat=True)) == [-4, 10]


@pytest.mark.django_db
def test_cannot_go_negative(make_member):
    member = make_member()
    ledger_service.post_entry(member, 3, R.SIGNUP_BONUS)

    with pytest.raises(InsufficientKeys, match="need 2 more"):
        ledger_service.post_entry(member, -5, R.REDEEM)

    assert keys_selector.balance_of(member) == 3
    assert KeysEntry.objects.count() == 1


@pytest.mark.django_db
def test_reference_makes_posting_idempotent(make_member):
    member = make_member()

    first = ledger_service.post_entry(member, 10, R.SEAL_PURCHASE, reference="intent:LS1")
    again = ledger_service.post_entry(member, 10, R.SEAL_PURCHASE, reference="intent:LS1")

    assert first.pk == again.pk
    assert keys_selector.balance_of(member) == 10


@pytest.mark.django_db
def test_zero_delta_is_refused(make_member):
    with pytest.raises(ValueError):
        ledger_service.post_entry(make_member(), 0, R.ADMIN_ADJUST)


@pytest.mark.django_db
def test_admin_adjust_requires_note(make_member, staff_user):
    member = make_member()

    with pytest.raises(ValueError):
        ledger_service.admin_adjust(member, 5, "  ", staff_user)
    entry = ledger_service.admin_adjust(member, 5, "Birthday gift", staff_user)

    assert entry.created_by == staff_user
    assert entry.reason == R.ADMIN_ADJUST


@pytest.mark.django_db
def test_database_rejects_negative_balance_even_without_service(make_member):
    account = KeysAccount.objects.create(member=make_member(), balance=0)

    with pytest.raises(IntegrityError), transaction.atomic():
        KeysAccount.objects.filter(pk=account.pk).update(balance=-1)


@pytest.mark.django_db(transaction=True)
def test_concurrent_spends_never_overdraw(make_member):
    """
    Ten threads each try to spend 3 keys from a balance of 10. Exactly three
    must succeed, the balance must end at 1, and the ledger must add up.
    """
    member = make_member()
    ledger_service.post_entry(member, 10, R.SIGNUP_BONUS)

    barrier = threading.Barrier(10)
    results = []
    lock = threading.Lock()

    def spend():
        try:
            barrier.wait()  # start together to maximise contention
            ledger_service.post_entry(member, -3, R.REDEEM)
            outcome = "ok"
        except InsufficientKeys:
            outcome = "refused"
        finally:
            connection.close()  # each thread has its own DB connection
        with lock:
            results.append(outcome)

    threads = [threading.Thread(target=spend) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert results.count("ok") == 3
    assert results.count("refused") == 7
    assert keys_selector.balance_of(member) == 1
    deltas = list(KeysEntry.objects.filter(account__member=member).values_list("delta", flat=True))
    assert sum(deltas) == 1
    assert min(KeysEntry.objects.values_list("balance_after", flat=True)) >= 0
