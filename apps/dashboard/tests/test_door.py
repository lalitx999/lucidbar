import datetime as dt

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.bookings.models import Booking
from apps.bookings.services import booking_service
from apps.checkin.models import CheckIn
from apps.checkin.services import card_service
from apps.core.clock import business_night

pytestmark = pytest.mark.django_db


def test_dashboard_home_opens_the_door(client, staff_user):
    client.force_login(staff_user)

    assert client.get(reverse("dashboard:home"))["Location"] == reverse("dashboard:door")


def test_members_cannot_scan(client, make_member):
    member = make_member()
    client.force_login(member)

    response = client.post(reverse("dashboard:door_scan"), {"token": card_service.make_token(member)})

    assert response.status_code == 403
    assert not CheckIn.objects.exists()


def test_scan_checks_in_and_shows_member(client, staff_user, seal_member):
    member = seal_member(full_name="Velvet Guest")
    # Created directly: through the service a slot tonight may already be past.
    booking = Booking.objects.create(
        reference="BTEST01",
        member=member,
        night=business_night(),
        time_slot="01:00",
        starts_at=timezone.now(),
        area="salon",
        guests=2,
        note="Champagne ready",
    )
    client.force_login(staff_user)

    response = client.post(reverse("dashboard:door_scan"), {"token": card_service.make_token(member)}, follow=True)

    html = response.content.decode()
    checkin = CheckIn.objects.get()
    assert response.redirect_chain[-1][0].endswith(f"?last={checkin.pk}")
    assert "Velvet Guest checked in" in html
    assert "Bronze" in html  # current seal shown to door staff
    assert booking.get_area_display() in html and "Champagne ready" in html


def test_second_scan_warns(client, staff_user, make_member):
    member = make_member(full_name="Repeat Visitor")
    token = card_service.make_token(member)
    client.force_login(staff_user)
    client.post(reverse("dashboard:door_scan"), {"token": token})

    html = client.post(reverse("dashboard:door_scan"), {"token": token}, follow=True).content.decode()

    assert "already checked in tonight" in html
    assert CheckIn.objects.count() == 1


def test_bad_card_shows_error(client, staff_user):
    client.force_login(staff_user)

    html = client.post(reverse("dashboard:door_scan"), {"token": "garbage"}, follow=True).content.decode()

    assert "not a Lucid identity card" in html


def test_door_ignores_bad_last_param(client, staff_user):
    client.force_login(staff_user)

    assert client.get(reverse("dashboard:door"), {"last": "abc"}).status_code == 200


def test_door_page_query_count(client, staff_user, make_member, django_assert_max_num_queries):
    from apps.checkin.services import checkin_service

    for _ in range(5):
        checkin_service.check_in(make_member(), staff_user)
    last = CheckIn.objects.first()
    client.force_login(staff_user)

    with django_assert_max_num_queries(10):
        client.get(reverse("dashboard:door"), {"last": last.pk})


def test_booking_for_tomorrow_is_not_tonight(staff_user, make_member):
    from apps.bookings.selectors import booking_selector

    member = make_member()
    booking_service.request_booking(
        member, night=business_night() + dt.timedelta(days=1), time_slot="20:00", area="club", guests=1
    )

    assert booking_selector.tonight_for_member(member) is None
