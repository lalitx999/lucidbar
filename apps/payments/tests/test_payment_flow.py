"""End-to-end payment flow through views, Celery (eager) and a mocked EasySlip."""

from datetime import timedelta
from unittest import mock

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils import timezone

from apps.memberships.models import Membership, SealTier
from apps.memberships.selectors import membership_selector
from apps.payments.clients.easyslip import EasySlipResult, EasySlipTemporaryError
from apps.payments.models import PaymentIntent, PaymentSlip
from apps.payments.services import payment_service

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.usefixtures("seal_tiers")]

VERIFY = "apps.payments.tasks.easyslip.verify_slip"


def easyslip_ok(trans_ref="REF123456789", amount=499.00, when=None):
    return EasySlipResult(
        ok=True,
        data={
            "isDuplicate": False,
            "matchedAccount": None,
            "isAmountMatched": True,
            "rawSlip": {
                "transRef": trans_ref,
                "date": (when or timezone.now()).isoformat(),
                "amount": {"amount": amount},
                "receiver": {"account": {"bank": {"type": "BANKAC", "account": "xxx-x-x3743-x"}}},
            },
        },
    )


@pytest.fixture
def gold():
    return SealTier.objects.get(code="gold")


@pytest.fixture
def member(make_member, client):
    m = make_member()
    client.force_login(m)
    return m


def checkout(client, tier_code="gold"):
    response = client.post(reverse("payments:choose_seal"), {"tier": tier_code})
    assert response.status_code == 302
    return PaymentIntent.objects.latest("created_at")


def upload(client, intent, file):
    return client.post(reverse("payments:upload_slip", args=[intent.reference]), {"slip": file})


# ---------------------------------------------------------------------------
# Checkout
# ---------------------------------------------------------------------------
def test_seeded_tiers_exist():
    # Values come from the seed migration (0003_seed_seal_tiers).
    assert list(SealTier.objects.values_list("code", "price_satang")) == [
        ("bronze", 0),
        ("gold", 49900),
        ("obsidian", 99000),
    ]


def test_checkout_creates_intent_with_tier_price(client, member, gold):
    intent = checkout(client)

    assert intent.member == member
    assert intent.amount_satang == gold.price_satang
    assert intent.status == PaymentIntent.Status.AWAITING_SLIP
    assert intent.reference.startswith("LS")


def test_checkout_twice_reuses_open_intent(client, member):
    first = checkout(client)
    client.post(reverse("payments:choose_seal"), {"tier": "gold"})

    assert PaymentIntent.objects.count() == 1
    assert PaymentIntent.objects.get().pk == first.pk


def test_switching_tier_cancels_unpaid_checkout(client, member):
    first = checkout(client, "gold")
    second = checkout(client, "obsidian")

    first.refresh_from_db()
    assert first.status == PaymentIntent.Status.CANCELLED
    assert second.amount_satang == 99000


def test_free_tier_cannot_be_bought(client, member):
    response = client.post(reverse("payments:choose_seal"), {"tier": "bronze"}, follow=True)

    assert not PaymentIntent.objects.exists()
    assert "cannot be purchased" in response.content.decode()


def test_pay_page_shows_bank_and_promptpay_qr(client, member):
    intent = checkout(client)

    html = client.get(reverse("payments:pay", args=[intent.reference])).content.decode()

    assert "7811737430" in html
    assert "<svg" in html and "viewBox" in html  # inline PromptPay QR
    assert "499.00" in html


def test_member_cannot_see_someone_elses_payment(client, member, make_member, gold):
    other = make_member()
    intent = payment_service.start_checkout(other, gold)

    assert client.get(reverse("payments:pay", args=[intent.reference])).status_code == 404
    assert client.get(reverse("payments:status", args=[intent.reference])).status_code == 404


def test_expired_checkout_refuses_slip(client, member, slip_file):
    intent = checkout(client)
    PaymentIntent.objects.filter(pk=intent.pk).update(expires_at=timezone.now() - timedelta(minutes=1))

    with mock.patch(VERIFY) as verify:
        upload(client, intent, slip_file())

    intent.refresh_from_db()
    assert intent.status == PaymentIntent.Status.EXPIRED
    assert not verify.called


# ---------------------------------------------------------------------------
# Slip verification
# ---------------------------------------------------------------------------
def test_good_slip_approves_and_grants_gold(client, member, slip_file, gold):
    intent = checkout(client)

    with mock.patch(VERIFY, return_value=easyslip_ok()), mock.patch("apps.notifications.tasks.telegram") as tg:
        upload(client, intent, slip_file())

    intent.refresh_from_db()
    assert intent.status == PaymentIntent.Status.APPROVED
    slip = intent.slips.get()
    assert slip.status == PaymentSlip.Status.VERIFIED
    assert slip.trans_ref == "REF123456789"
    current = membership_selector.current_membership(member)
    assert current.tier == gold
    assert current.payment_intent == intent
    assert (current.ends_at - current.starts_at).days == 30
    assert tg.send_photo.called


def test_slip_image_is_reencoded_as_jpeg(client, member, slip_file):
    intent = checkout(client)

    with mock.patch(VERIFY, return_value=easyslip_ok()) as verify:
        upload(client, intent, slip_file())

    sent_bytes = verify.call_args.args[0]
    assert sent_bytes[:3] == b"\xff\xd8\xff"  # JPEG magic number
    assert verify.call_args.args[1] == 49900


def test_wrong_amount_lets_member_upload_again(client, member, slip_file):
    intent = checkout(client)

    with mock.patch(VERIFY, return_value=easyslip_ok(amount=400.00)):
        upload(client, intent, slip_file())

    intent.refresh_from_db()
    assert intent.status == PaymentIntent.Status.AWAITING_SLIP
    assert "does not match" in intent.status_message
    assert intent.slips.get().status == PaymentSlip.Status.REJECTED


def test_same_bank_reference_cannot_pay_twice(client, member, make_member, slip_file, gold):
    intent = checkout(client)
    with mock.patch(VERIFY, return_value=easyslip_ok(trans_ref="SAMEREF")):
        upload(client, intent, slip_file())

    other = make_member()
    client.force_login(other)
    other_intent = checkout(client)
    with mock.patch(VERIFY, return_value=easyslip_ok(trans_ref="SAMEREF")):
        upload(client, other_intent, slip_file())

    other_intent.refresh_from_db()
    assert other_intent.status == PaymentIntent.Status.AWAITING_SLIP
    assert "already been used" in other_intent.status_message
    assert not Membership.objects.filter(member=other, source="payment").exists()


def test_same_image_cannot_be_uploaded_twice(client, member, make_member, slip_file):
    image = slip_file(color=(1, 2, 3))
    intent = checkout(client)
    with mock.patch(VERIFY, return_value=easyslip_ok()):
        upload(client, intent, image)

    other = make_member()
    client.force_login(other)
    other_intent = checkout(client)
    image.seek(0)
    with mock.patch(VERIFY) as verify:
        response = upload(client, other_intent, image)

    assert not verify.called
    assert "already been uploaded" in client.get(response["Location"]).content.decode()


def test_unclear_receiver_goes_to_staff_review(client, member, slip_file):
    intent = checkout(client)
    result = easyslip_ok()
    result.data["rawSlip"]["receiver"] = {"account": {"bank": {"account": "xxx-x-x0000-x"}}}

    with mock.patch(VERIFY, return_value=result), mock.patch("apps.notifications.tasks.telegram") as tg:
        upload(client, intent, slip_file())

    intent.refresh_from_db()
    assert intent.status == PaymentIntent.Status.REVIEW
    assert tg.send_photo.called
    assert not Membership.objects.filter(member=member, source="payment").exists()


def test_temporary_errors_end_in_review_not_stuck(client, member, slip_file):
    intent = checkout(client)

    with (
        mock.patch(VERIFY, side_effect=EasySlipTemporaryError("API_SERVER_ERROR")),
        mock.patch("apps.payments.tasks.verify_slip_task.retry", side_effect=Exception("retry")) as retry,
        mock.patch("apps.notifications.tasks.telegram"),
    ):
        # In eager mode we simulate the final attempt by pretending retries are exhausted.
        with mock.patch("apps.payments.tasks.MAX_RETRIES", 0):
            upload(client, intent, slip_file())

    intent.refresh_from_db()
    assert intent.status == PaymentIntent.Status.REVIEW
    assert not retry.called


def test_non_image_upload_is_refused(client, member):
    intent = checkout(client)
    fake = SimpleUploadedFile("slip.png", b"%PDF-1.4 not an image", content_type="image/png")

    with mock.patch(VERIFY) as verify:
        response = upload(client, intent, fake)

    assert not verify.called
    assert "not a valid image" in client.get(response["Location"]).content.decode()


def test_status_endpoint_reports_state(client, member):
    intent = checkout(client)

    data = client.get(reverse("payments:status", args=[intent.reference])).json()

    assert data["status"] == "awaiting_slip"
    assert data["done"] is True


def test_cancel_unpaid_checkout(client, member):
    intent = checkout(client)

    client.post(reverse("payments:cancel", args=[intent.reference]))

    intent.refresh_from_db()
    assert intent.status == PaymentIntent.Status.CANCELLED


def test_renewal_extends_from_current_end(member, gold):
    first = payment_service.start_checkout(member, gold)
    PaymentIntent.objects.filter(pk=first.pk).update(status=PaymentIntent.Status.APPROVED)
    from apps.memberships.services import membership_service

    m1 = membership_service.grant_paid_membership(member, gold, first)
    second = payment_service.start_checkout(member, gold)
    m2 = membership_service.grant_paid_membership(member, gold, second)

    assert m2.starts_at == m1.ends_at
