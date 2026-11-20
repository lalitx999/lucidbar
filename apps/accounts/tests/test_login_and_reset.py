import pytest
from django.core import mail
from django.test import override_settings
from django.urls import reverse

from apps.accounts.models import Member

from .conftest import PASSWORD, last_code

pytestmark = pytest.mark.django_db(transaction=True)


def _login(client, email, password=PASSWORD, **extra):
    return client.post(reverse("accounts:login"), {"email": email, "password": password}, **extra)


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------
def test_active_member_can_log_in_with_any_email_case(client, make_member):
    member = make_member()

    response = _login(client, member.email.upper())

    assert response.status_code == 302
    assert response["Location"] == reverse("core:portal")


def test_wrong_password_shows_generic_error(client, make_member):
    member = make_member()

    response = _login(client, member.email, "wrong-password")

    assert response.status_code == 200
    assert "Incorrect email or password" in response.content.decode()


def test_pending_member_is_sent_to_verification(client, make_member):
    member = make_member(status=Member.Status.PENDING)

    response = _login(client, member.email)

    assert response["Location"] == reverse("accounts:verify")
    assert "_auth_user_id" not in client.session  # not signed in yet


def test_suspended_member_cannot_log_in(client, make_member):
    member = make_member(status=Member.Status.SUSPENDED)

    response = _login(client, member.email)

    assert response.status_code == 200
    assert "Incorrect email or password" in response.content.decode()


@override_settings(LOGIN_MAX_FAILURES=3)
def test_login_is_locked_after_repeated_failures(client, make_member):
    member = make_member()
    for _ in range(3):
        _login(client, member.email, "wrong-password")

    response = _login(client, member.email)  # correct password, still locked

    assert response.status_code == 200
    assert "Too many failed attempts" in response.content.decode()


def test_forged_x_real_ip_is_ignored_outside_production(client, make_member, settings):
    assert settings.TRUST_X_REAL_IP is False
    member = make_member()
    settings.LOGIN_MAX_FAILURES = 1
    # Each request claims a different IP; the limiter must still see REMOTE_ADDR.
    for i in range(5):
        _login(client, f"nobody{i}@example.com", "x", HTTP_X_REAL_IP=f"10.0.0.{i}")

    response = _login(client, member.email)

    assert "Too many failed attempts" in response.content.decode()


def test_logout_requires_post(client, make_member):
    member = make_member()
    client.force_login(member)

    assert client.get(reverse("accounts:logout")).status_code == 405
    response = client.post(reverse("accounts:logout"))
    assert response["Location"] == reverse("core:welcome")
    assert client.get(reverse("core:portal")).status_code == 302


# ---------------------------------------------------------------------------
# Password reset
# ---------------------------------------------------------------------------
def test_reset_flow_sets_new_password(client, make_member):
    member = make_member()
    client.post(reverse("accounts:password_reset"), {"email": member.email})
    new_password = "Velvet-Chamber-9931"

    response = client.post(
        reverse("accounts:password_reset_confirm"),
        {"code": last_code(), "new_password": new_password, "new_password_confirm": new_password},
    )

    assert response["Location"] == reverse("accounts:login")
    member.refresh_from_db()
    assert member.check_password(new_password)


def test_reset_request_does_not_reveal_unknown_email(client):
    response = client.post(reverse("accounts:password_reset"), {"email": "ghost@example.com"}, follow=True)

    assert "If an account exists" in response.content.decode()
    assert not mail.outbox


def test_reset_with_wrong_code_keeps_old_password(client, make_member):
    member = make_member()
    client.post(reverse("accounts:password_reset"), {"email": member.email})
    code = last_code()
    wrong = "000000" if code != "000000" else "111111"

    response = client.post(
        reverse("accounts:password_reset_confirm"),
        {"code": wrong, "new_password": "Velvet-Chamber-9931", "new_password_confirm": "Velvet-Chamber-9931"},
    )

    assert response.status_code == 200
    member.refresh_from_db()
    assert member.check_password(PASSWORD)


def test_reset_activates_pending_member(client, make_member):
    member = make_member(status=Member.Status.PENDING)
    client.post(reverse("accounts:password_reset"), {"email": member.email})
    new_password = "Velvet-Chamber-9931"

    client.post(
        reverse("accounts:password_reset_confirm"),
        {"code": last_code(), "new_password": new_password, "new_password_confirm": new_password},
    )

    member.refresh_from_db()
    assert member.status == Member.Status.ACTIVE


def test_suspended_member_gets_no_reset_email(client, make_member):
    member = make_member(status=Member.Status.SUSPENDED)

    client.post(reverse("accounts:password_reset"), {"email": member.email})

    assert not mail.outbox
