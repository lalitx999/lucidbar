import datetime as dt

import pytest
from django.urls import reverse

from apps.bookings.models import Booking
from apps.bookings.services import booking_service
from apps.core.clock import business_night

pytestmark = pytest.mark.django_db


def _booking(member, days=1):
    return booking_service.request_booking(
        member, night=business_night() + dt.timedelta(days=days), time_slot="22:00", area="seating", guests=2
    )


def test_members_cannot_open_bookings_dashboard(client, make_member):
    client.force_login(make_member())

    assert client.get(reverse("dashboard:bookings")).status_code == 403


def test_staff_sees_requests_and_confirms(client, staff_user, make_member):
    booking = _booking(make_member(full_name="Night Owl"))
    client.force_login(staff_user)

    html = client.get(reverse("dashboard:bookings")).content.decode()
    assert "Night Owl" in html and booking.reference in html

    client.post(reverse("dashboard:booking_confirm", args=[booking.pk]), {"note": "Booth 3"})
    booking.refresh_from_db()
    assert booking.status == Booking.Status.CONFIRMED
    assert booking.staff_note == "Booth 3"


def test_decline_without_reason_is_refused(client, staff_user, make_member):
    booking = _booking(make_member())
    client.force_login(staff_user)

    client.post(reverse("dashboard:booking_decline", args=[booking.pk]), {"note": ""})
    booking.refresh_from_db()
    assert booking.status == Booking.Status.REQUESTED

    client.post(reverse("dashboard:booking_decline", args=[booking.pk]), {"note": "Private event"})
    booking.refresh_from_db()
    assert booking.status == Booking.Status.DECLINED


def test_search_by_reference(client, staff_user, make_member):
    booking = _booking(make_member())
    client.force_login(staff_user)

    html = client.get(reverse("dashboard:bookings"), {"q": booking.reference.lower()}).content.decode()

    assert "Search results" in html and booking.reference in html


def test_bookings_page_query_count(client, staff_user, make_member, django_assert_max_num_queries):
    for i in range(5):
        _booking(make_member(), days=i + 1)
    client.force_login(staff_user)

    with django_assert_max_num_queries(8):
        client.get(reverse("dashboard:bookings"))
