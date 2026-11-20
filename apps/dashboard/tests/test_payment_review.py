from unittest import mock

import pytest
from django.core.files.base import ContentFile
from django.urls import reverse

from apps.memberships.models import Membership, SealTier
from apps.payments.models import PaymentIntent, PaymentSlip
from apps.payments.services import payment_service
from tests.fixtures import make_image_bytes

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.usefixtures("seal_tiers")]


@pytest.fixture
def review_intent(make_member):
    member = make_member()
    intent = payment_service.start_checkout(member, SealTier.objects.get(code="gold"))
    slip = PaymentSlip(intent=intent, sha256="a" * 64, status=PaymentSlip.Status.REVIEW, note="Receiver unclear")
    slip.image.save("slip.jpg", ContentFile(make_image_bytes(fmt="JPEG")), save=False)
    slip.save()
    PaymentIntent.objects.filter(pk=intent.pk).update(status=PaymentIntent.Status.REVIEW)
    intent.refresh_from_db()
    return intent


def test_dashboard_requires_staff(client, make_member, review_intent):
    assert client.get(reverse("dashboard:payments")).status_code == 302  # anonymous -> login

    client.force_login(make_member())
    assert client.get(reverse("dashboard:payments")).status_code == 403
    slip = review_intent.slips.get()
    assert client.get(reverse("dashboard:slip_image", args=[slip.pk])).status_code == 403


def test_queue_lists_payments_under_review(client, staff_user, review_intent, django_assert_max_num_queries):
    client.force_login(staff_user)

    with django_assert_max_num_queries(5):
        html = client.get(reverse("dashboard:payments")).content.decode()

    assert review_intent.reference in html


def test_staff_can_view_slip_image_privately(client, staff_user, review_intent):
    client.force_login(staff_user)
    slip = review_intent.slips.get()

    response = client.get(reverse("dashboard:slip_image", args=[slip.pk]))

    assert response.status_code == 200
    assert response["Content-Type"] == "image/jpeg"
    assert "no-store" in response["Cache-Control"]


def test_staff_approve_grants_membership(client, staff_user, review_intent):
    client.force_login(staff_user)

    with mock.patch("apps.notifications.tasks.telegram"):
        client.post(reverse("dashboard:payment_approve", args=[review_intent.reference]), {"trans_ref": "BANK1"})

    review_intent.refresh_from_db()
    assert review_intent.status == PaymentIntent.Status.APPROVED
    assert review_intent.decided_by == staff_user
    assert review_intent.slips.get().trans_ref == "BANK1"
    assert Membership.objects.filter(member=review_intent.member, source="payment").exists()


def test_staff_reject_lets_member_try_again(client, staff_user, review_intent):
    client.force_login(staff_user)

    client.post(
        reverse("dashboard:payment_reject", args=[review_intent.reference]),
        {"reason": "Amount does not match", "allow_new_slip": "on"},
    )

    review_intent.refresh_from_db()
    assert review_intent.status == PaymentIntent.Status.AWAITING_SLIP
    assert review_intent.status_message == "Amount does not match"
    assert review_intent.slips.get().status == PaymentSlip.Status.REJECTED


def test_staff_reject_final(client, staff_user, review_intent):
    client.force_login(staff_user)

    client.post(reverse("dashboard:payment_reject", args=[review_intent.reference]), {"reason": "Fraud suspected"})

    review_intent.refresh_from_db()
    assert review_intent.status == PaymentIntent.Status.REJECTED


def test_cannot_approve_twice(client, staff_user, review_intent):
    client.force_login(staff_user)
    with mock.patch("apps.notifications.tasks.telegram"):
        client.post(reverse("dashboard:payment_approve", args=[review_intent.reference]))
        client.post(reverse("dashboard:payment_approve", args=[review_intent.reference]))

    assert Membership.objects.filter(member=review_intent.member, source="payment").count() == 1
