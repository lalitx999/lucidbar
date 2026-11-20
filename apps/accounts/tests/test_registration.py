from datetime import date

import pytest
from django.core import mail
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import Member

from .conftest import last_code

pytestmark = pytest.mark.django_db(transaction=True)


def test_register_creates_pending_member_and_emails_code(client, registration_payload):
    response = client.post(reverse("accounts:register"), registration_payload)

    assert response.status_code == 302
    assert response["Location"] == reverse("accounts:verify")
    member = Member.objects.get()
    assert member.email == "arthur@example.com"  # stored lower-case
    assert member.phone == "812345678"  # leading trunk zero dropped
    assert member.status == Member.Status.PENDING
    assert member.handle.startswith("lucid_")
    assert member.check_password(registration_payload["password"])
    assert len(mail.outbox) == 1


def test_full_flow_register_verify_lands_in_portal(client, registration_payload):
    client.post(reverse("accounts:register"), registration_payload)

    response = client.post(reverse("accounts:verify"), {"code": last_code()})

    assert response.status_code == 302
    assert response["Location"] == reverse("core:portal")
    member = Member.objects.get()
    assert member.status == Member.Status.ACTIVE
    assert member.email_verified_at is not None
    assert client.get(reverse("core:portal")).status_code == 200


def test_wrong_code_shows_error_and_keeps_member_pending(client, registration_payload):
    client.post(reverse("accounts:register"), registration_payload)
    code = last_code()
    wrong = "000000" if code != "000000" else "111111"

    response = client.post(reverse("accounts:verify"), {"code": wrong})

    assert response.status_code == 200
    assert "attempts left" in response.content.decode()
    assert Member.objects.get().status == Member.Status.PENDING


def test_underage_is_rejected(client, registration_payload):
    today = timezone.localdate()
    nineteen = date(today.year - 19, today.month, min(today.day, 28))
    registration_payload["date_of_birth"] = nineteen.isoformat()

    response = client.post(reverse("accounts:register"), registration_payload)

    assert response.status_code == 200
    assert "aged 20 and over" in response.content.decode()
    assert not Member.objects.exists()
    assert not mail.outbox


def test_exactly_twenty_today_is_accepted(client, registration_payload):
    today = timezone.localdate()
    if (today.month, today.day) == (2, 29):
        pytest.skip("leap day")
    registration_payload["date_of_birth"] = date(today.year - 20, today.month, today.day).isoformat()

    response = client.post(reverse("accounts:register"), registration_payload)

    assert response.status_code == 302


def test_duplicate_email_is_case_insensitive(client, registration_payload, make_member):
    make_member(email="arthur@example.com")
    registration_payload["email"] = "ARTHUR@EXAMPLE.COM"

    response = client.post(reverse("accounts:register"), registration_payload)

    assert response.status_code == 200
    assert "already exists" in response.content.decode()


def test_duplicate_phone_is_rejected(client, registration_payload, make_member):
    make_member(phone="812345678")

    response = client.post(reverse("accounts:register"), registration_payload)

    assert response.status_code == 200
    assert "already registered" in response.content.decode()


def test_weak_or_mismatched_password_is_rejected(client, registration_payload):
    registration_payload["password"] = "12345678"
    registration_payload["password_confirm"] = "different"

    response = client.post(reverse("accounts:register"), registration_payload)

    html = response.content.decode()
    assert response.status_code == 200
    assert "Passwords do not match" in html
    assert not Member.objects.exists()


def test_terms_must_be_accepted(client, registration_payload):
    registration_payload.pop("accept_terms")

    response = client.post(reverse("accounts:register"), registration_payload)

    assert response.status_code == 200
    assert not Member.objects.exists()


def test_resend_sends_new_code(client, registration_payload):
    client.post(reverse("accounts:register"), registration_payload)

    response = client.post(reverse("accounts:resend_code"))

    assert response.status_code == 302
    assert len(mail.outbox) == 2


def test_verify_without_pending_session_redirects_to_login(client):
    response = client.get(reverse("accounts:verify"))

    assert response.status_code == 302
    assert response["Location"] == reverse("accounts:login")


def test_register_page_renders(client):
    response = client.get(reverse("accounts:register"))

    assert response.status_code == 200
    assert 'name="date_of_birth"' in response.content.decode()
