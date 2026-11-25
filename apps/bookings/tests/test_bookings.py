import datetime as dt
import threading
from unittest import mock

import pytest
from django.db import connection
from django.urls import reverse
from django.utils import timezone

from apps.bookings.models import Booking
from apps.bookings.services import booking_service
from apps.core.clock import business_night, night_start
from apps.whispers.models import Whisper

NOTIFY = "apps.notifications.tasks.telegram"


def _tomorrow():
    return business_night() + dt.timedelta(days=1)


def _request(member, night=None, time_slot="21:00", **extra):
    payload = {"night": night or _tomorrow(), "time_slot": time_slot, "area": "seating", "guests": 4}
    payload.update(extra)
    return booking_service.request_booking(member, **payload)


# ---------------------------------------------------------------------------
# Club night arithmetic
# ---------------------------------------------------------------------------
@pytest.mark.django_db
def test_late_slots_belong_to_the_night_before():
    night = dt.date(2026, 11, 27)  # Friday

    assert timezone.localtime(night_start(night, dt.time(23))).date() == night
    assert timezone.localtime(night_start(night, dt.time(1))).date() == dt.date(2026, 11, 28)


def test_business_night_turns_over_in_the_morning():
    bangkok = dt.timezone(dt.timedelta(hours=7))

    assert business_night(dt.datetime(2026, 11, 28, 1, 30, tzinfo=bangkok)) == dt.date(2026, 11, 27)
    assert business_night(dt.datetime(2026, 11, 28, 7, 0, tzinfo=bangkok)) == dt.date(2026, 11, 28)


# ---------------------------------------------------------------------------
# Requesting
# ---------------------------------------------------------------------------
@pytest.mark.django_db(transaction=True)
def test_request_creates_booking_whisper_and_staff_alert(make_member):
    member = make_member()

    with mock.patch(NOTIFY) as tg:
        booking = _request(member, time_slot="01:00", note="  Birthday  ")

    assert booking.status == Booking.Status.REQUESTED
    assert booking.reference.startswith("B") and len(booking.reference) == 7
    assert booking.note == "Birthday"
    assert timezone.localtime(booking.starts_at).date() == booking.night + dt.timedelta(days=1)
    assert Whisper.objects.filter(member=member, kind=Whisper.Kind.BOOKING).count() == 1
    text = tg.send_message.call_args.args[0]
    assert booking.reference in text and "Birthday" in text


@pytest.mark.django_db
def test_past_time_is_refused(make_member):
    with pytest.raises(booking_service.BookingError, match="not passed"):
        _request(make_member(), night=business_night() - dt.timedelta(days=1))


@pytest.mark.django_db
def test_too_far_ahead_is_refused(make_member, settings):
    settings.BOOKING_MAX_DAYS_AHEAD = 10

    with pytest.raises(booking_service.BookingError, match="10 days ahead"):
        _request(make_member(), night=business_night() + dt.timedelta(days=11))


@pytest.mark.django_db
def test_one_open_booking_per_night(make_member):
    member = make_member()
    _request(member)

    with pytest.raises(booking_service.BookingError, match="already have a booking"):
        _request(member, time_slot="23:00")


@pytest.mark.django_db
def test_cancelled_night_can_be_booked_again(make_member):
    member = make_member()
    booking_service.cancel(_request(member), member)

    assert _request(member).status == Booking.Status.REQUESTED


@pytest.mark.django_db
def test_open_booking_limit(make_member, settings):
    settings.BOOKING_MAX_OPEN = 2
    member = make_member()
    _request(member, night=_tomorrow())
    _request(member, night=_tomorrow() + dt.timedelta(days=1))

    with pytest.raises(booking_service.BookingError, match="up to 2"):
        _request(member, night=_tomorrow() + dt.timedelta(days=2))


@pytest.mark.django_db(transaction=True)
def test_concurrent_requests_for_one_night_create_one(make_member):
    member = make_member()
    barrier = threading.Barrier(4)
    outcomes = []

    def attempt():
        try:
            barrier.wait()
            with mock.patch(NOTIFY):
                _request(member)
            outcomes.append("ok")
        except booking_service.BookingError:
            outcomes.append("refused")
        finally:
            connection.close()

    threads = [threading.Thread(target=attempt) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert outcomes.count("ok") == 1
    assert Booking.objects.count() == 1


# ---------------------------------------------------------------------------
# Cancelling, confirming, declining
# ---------------------------------------------------------------------------
@pytest.mark.django_db
def test_member_cannot_cancel_someone_elses_booking(make_member):
    booking = _request(make_member())

    with pytest.raises(booking_service.BookingError):
        booking_service.cancel(booking, make_member())


@pytest.mark.django_db
def test_started_booking_cannot_be_cancelled(make_member):
    member = make_member()
    booking = _request(member)
    Booking.objects.filter(pk=booking.pk).update(starts_at=timezone.now() - dt.timedelta(minutes=1))

    with pytest.raises(booking_service.BookingError, match="no longer"):
        booking_service.cancel(booking, member)


@pytest.mark.django_db(transaction=True)
def test_cancelling_a_confirmed_booking_alerts_staff(make_member, staff_user):
    member = make_member()
    with mock.patch(NOTIFY):
        booking = _request(member)
    booking_service.confirm(booking, staff_user)

    with mock.patch(NOTIFY) as tg:
        booking_service.cancel(booking, member)

    assert "cancelled" in tg.send_message.call_args.args[0]


@pytest.mark.django_db
def test_confirm_sends_whisper_with_note(make_member, staff_user):
    member = make_member()
    booking = _request(member)

    booking_service.confirm(booking, staff_user, "Table 7")

    booking.refresh_from_db()
    assert booking.status == Booking.Status.CONFIRMED
    assert booking.handled_by == staff_user
    whisper = Whisper.objects.filter(member=member).order_by("-id").first()
    assert whisper.title == "Your booking is confirmed"
    assert "Table 7" in whisper.body
    with pytest.raises(booking_service.BookingError):
        booking_service.confirm(booking, staff_user)


@pytest.mark.django_db
def test_decline_needs_a_reason(make_member, staff_user):
    booking = _request(make_member())

    with pytest.raises(booking_service.BookingError, match="short message"):
        booking_service.decline(booking, staff_user, "  ")
    booking_service.decline(booking, staff_user, "Fully booked that night")

    booking.refresh_from_db()
    assert booking.status == Booking.Status.DECLINED


# ---------------------------------------------------------------------------
# Views
# ---------------------------------------------------------------------------
@pytest.mark.django_db
def test_chamber_page_books_and_lists(client, make_member):
    member = make_member()
    client.force_login(member)
    payload = {"night": _tomorrow().isoformat(), "time_slot": "20:00", "area": "salon", "guests": 3, "note": ""}

    response = client.post(reverse("bookings:chamber"), payload, follow=True)

    html = response.content.decode()
    booking = Booking.objects.get(member=member)
    assert booking.area == Booking.Area.SALON
    assert booking.reference in html
    assert "Private salon" in html


@pytest.mark.django_db
def test_chamber_form_limits_guests(client, make_member, settings):
    settings.BOOKING_MAX_GUESTS = 15
    client.force_login(make_member())
    payload = {"night": _tomorrow().isoformat(), "time_slot": "20:00", "area": "club", "guests": 16}

    response = client.post(reverse("bookings:chamber"), payload)

    assert response.status_code == 200
    assert not Booking.objects.exists()


@pytest.mark.django_db
def test_cancel_view_only_finds_own_booking(client, make_member):
    owner, other = make_member(), make_member()
    booking = _request(owner)
    client.force_login(other)

    assert client.post(reverse("bookings:cancel", args=[booking.reference])).status_code == 404
    client.force_login(owner)
    client.post(reverse("bookings:cancel", args=[booking.reference]))
    booking.refresh_from_db()
    assert booking.status == Booking.Status.CANCELLED


@pytest.mark.django_db
def test_portal_links_to_chamber(client, make_member):
    client.force_login(make_member())

    assert reverse("bookings:chamber") in client.get(reverse("core:portal")).content.decode()
