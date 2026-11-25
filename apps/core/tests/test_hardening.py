import logging
import os
import subprocess
import sys
import uuid
from datetime import timedelta
from io import StringIO
from unittest import mock

import pytest
from django.conf import settings
from django.core.files.base import ContentFile
from django.core.management import call_command
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import EmailOTP, Member
from apps.core import tasks
from apps.notifications.logging import TelegramErrorHandler
from apps.payments.models import PaymentIntent, PaymentSlip
from apps.payments.services import payment_service
from tests.fixtures import make_image_bytes


# ---------------------------------------------------------------------------
# Headers and error pages
# ---------------------------------------------------------------------------
def test_security_headers(client):
    response = client.get(reverse("core:welcome"))

    assert "camera=(self)" in response["Permissions-Policy"]
    assert "geolocation=()" in response["Permissions-Policy"]
    assert response["X-Frame-Options"] == "DENY"
    assert response["Referrer-Policy"] == "same-origin"
    assert response["Cross-Origin-Opener-Policy"] == "same-origin"
    assert "default-src 'self'" in response["Content-Security-Policy"]


@pytest.mark.django_db
def test_themed_404(client):
    response = client.get("/no-such-page/")

    assert response.status_code == 404
    assert "Lost in the dark" in response.content.decode()


def test_500_page_renders_without_request_context():
    html = render_to_string("500.html")

    assert "Something went wrong" in html and "500" in html


# ---------------------------------------------------------------------------
# Production guards
# ---------------------------------------------------------------------------
def _boot_production(**overrides):
    env = {
        **os.environ,
        "DJANGO_SETTINGS_MODULE": "config.settings.production",
        "DJANGO_SECRET_KEY": "x" * 60,
        "DJANGO_ALLOWED_HOSTS": "example.com",
        "DJANGO_ADMIN_URL": "ops-1234/",
        "EASYSLIP_MODE": "off",
    }
    env.update(overrides)
    return subprocess.run(  # noqa: S603
        [sys.executable, "-c", "import django; django.setup()"],
        env=env,
        capture_output=True,
        text=True,
        cwd=settings.BASE_DIR,
        check=False,
    )


def test_production_boots_with_proper_settings():
    assert _boot_production().returncode == 0


@pytest.mark.parametrize(
    ("override", "message"),
    [
        ({"DJANGO_SECRET_KEY": "change-me"}, "DJANGO_SECRET_KEY"),
        ({"DJANGO_ADMIN_URL": "admin/"}, "DJANGO_ADMIN_URL"),
        ({"EASYSLIP_MODE": "fake"}, "fake"),
    ],
)
def test_production_refuses_unsafe_settings(override, message):
    result = _boot_production(**override)

    assert result.returncode != 0
    assert message in result.stderr


# ---------------------------------------------------------------------------
# Housekeeping jobs
# ---------------------------------------------------------------------------
def test_beat_schedule_points_at_real_tasks():
    from config.celery import app

    app.loader.import_default_modules()
    for entry in settings.CELERY_BEAT_SCHEDULE.values():
        assert entry["task"] in app.tasks, entry["task"]


@pytest.fixture
def intent(make_member, seal_tiers):
    from apps.memberships.models import SealTier

    return payment_service.start_checkout(make_member(), SealTier.objects.get(code="gold"))


def _slip(intent, days_old):
    slip = PaymentSlip(intent=intent, sha256=uuid.uuid4().hex * 2, status=PaymentSlip.Status.VERIFIED)
    slip.image.save("s.jpg", ContentFile(make_image_bytes(fmt="JPEG")), save=False)
    slip.save()
    PaymentSlip.objects.filter(pk=slip.pk).update(created_at=timezone.now() - timedelta(days=days_old))
    return slip


@pytest.mark.django_db
def test_unpaid_checkouts_expire(intent):
    PaymentIntent.objects.filter(pk=intent.pk).update(expires_at=timezone.now() - timedelta(minutes=1))

    assert tasks.expire_unpaid_checkouts() == 1
    intent.refresh_from_db()
    assert intent.status == PaymentIntent.Status.EXPIRED


@pytest.mark.django_db
def test_old_slip_images_of_finished_payments_are_deleted(intent, settings):
    settings.SLIP_RETENTION_DAYS = 30
    PaymentIntent.objects.filter(pk=intent.pk).update(status=PaymentIntent.Status.APPROVED)
    old, recent = _slip(intent, 40), _slip(intent, 5)
    old_name = old.image.name

    assert tasks.purge_old_slip_images() == 1

    old.refresh_from_db()
    recent.refresh_from_db()
    assert not old.image and recent.image
    assert not recent.image.storage.exists(old_name)


@pytest.mark.django_db
def test_slips_of_open_payments_are_kept(intent, settings):
    settings.SLIP_RETENTION_DAYS = 30
    PaymentIntent.objects.filter(pk=intent.pk).update(status=PaymentIntent.Status.REVIEW)
    slip = _slip(intent, 400)

    assert tasks.purge_old_slip_images() == 0
    slip.refresh_from_db()
    assert slip.image


@pytest.mark.django_db
def test_purged_slip_image_returns_404_to_manager(client, manager_user, intent):
    PaymentIntent.objects.filter(pk=intent.pk).update(status=PaymentIntent.Status.APPROVED)
    slip = _slip(intent, 1)
    PaymentSlip.objects.filter(pk=slip.pk).update(image="")
    client.force_login(manager_user)

    assert client.get(reverse("dashboard:slip_image", args=[slip.pk])).status_code == 404


@pytest.mark.django_db
def test_old_otps_are_purged(make_member):
    member = make_member()
    EmailOTP.objects.create(
        member=member, purpose="verify", code_hash="x", expires_at=timezone.now() - timedelta(days=2)
    )
    EmailOTP.objects.create(
        member=member, purpose="verify", code_hash="y", expires_at=timezone.now() + timedelta(minutes=5)
    )

    assert tasks.purge_old_otps() == 1
    assert EmailOTP.objects.count() == 1


# ---------------------------------------------------------------------------
# Abuse limits
# ---------------------------------------------------------------------------
@pytest.mark.django_db
def test_checkout_attempts_are_limited(make_member, seal_tiers, settings):
    from apps.memberships.models import SealTier

    settings.CHECKOUTS_PER_HOUR = 3
    member, gold = make_member(), SealTier.objects.get(code="gold")
    for _ in range(3):
        payment_service.start_checkout(member, gold)

    with pytest.raises(payment_service.PaymentError, match="Too many"):
        payment_service.start_checkout(member, gold)


@pytest.mark.django_db
def test_booking_requests_are_limited(make_member, settings):
    import datetime as dt

    from apps.bookings.services import booking_service
    from apps.core.clock import business_night

    settings.BOOKING_REQUESTS_PER_HOUR = 2
    member = make_member()
    for day in (1, 2):
        booking_service.request_booking(
            member, night=business_night() + dt.timedelta(days=day), time_slot="21:00", area="club", guests=1
        )

    with pytest.raises(booking_service.BookingError, match="Too many"):
        booking_service.request_booking(
            member, night=business_night() + dt.timedelta(days=3), time_slot="21:00", area="club", guests=1
        )


# ---------------------------------------------------------------------------
# Telegram error alerts
# ---------------------------------------------------------------------------
def _error_record(path="/portal/?email=secret@example.com"):
    request = mock.Mock(method="GET", path=path.split("?")[0], get_full_path=lambda: path)
    try:
        raise ValueError("boom")
    except ValueError:
        import sys as _sys

        record = logging.LogRecord(
            "django.request", logging.ERROR, __file__, 1, "Internal Server Error", None, _sys.exc_info()
        )
    record.request = request
    return record


def test_error_alert_sent_once_without_query_string(settings):
    settings.TELEGRAM_BOT_TOKEN = "t"
    handler = TelegramErrorHandler()

    with mock.patch("apps.notifications.tasks.notify_error.apply_async") as send:
        handler.emit(_error_record())
        handler.emit(_error_record())

    assert send.call_count == 1
    summary = send.call_args.kwargs["args"][0]
    assert "GET /portal/" in summary and "ValueError: boom" in summary
    assert "secret@example.com" not in summary


def test_error_alert_skipped_without_token_and_never_raises(settings):
    settings.TELEGRAM_BOT_TOKEN = ""
    handler = TelegramErrorHandler()
    with mock.patch("apps.notifications.tasks.notify_error.apply_async") as send:
        handler.emit(_error_record())
    assert not send.called

    settings.TELEGRAM_BOT_TOKEN = "t"
    with mock.patch("apps.notifications.tasks.notify_error.apply_async", side_effect=RuntimeError("broker down")):
        handler.emit(_error_record("/other/"))  # must not raise


# ---------------------------------------------------------------------------
# create_staff command
# ---------------------------------------------------------------------------
@pytest.mark.django_db
def test_create_staff_makes_manager(monkeypatch):
    monkeypatch.setattr("getpass.getpass", lambda prompt="": "Velvet-Chamber-9931")

    call_command(
        "create_staff",
        "Boss@Example.com",
        "--name",
        "Club Boss",
        "--phone",
        "899990000",
        "--manager",
        stdout=StringIO(),
    )

    staff = Member.objects.get(email="boss@example.com")
    assert staff.is_staff and staff.is_verified
    assert set(staff.groups.values_list("name", flat=True)) == {"Staff", "Manager"}
    assert staff.check_password("Velvet-Chamber-9931")


@pytest.mark.django_db
def test_create_staff_promotes_existing_without_touching_password(make_member, monkeypatch):
    member = make_member(email="door@example.com")
    monkeypatch.setattr("getpass.getpass", mock.Mock(side_effect=AssertionError("should not ask")))

    call_command("create_staff", "door@example.com", "--name", "Door", "--phone", "1", stdout=StringIO())

    member.refresh_from_db()
    assert member.is_staff
    assert not member.groups.filter(name="Manager").exists()
