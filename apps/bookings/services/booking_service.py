"""
VIP Chamber bookings: members request, staff confirm or decline, members may
cancel an upcoming booking. Every change leaves a whisper for the member.
"""

import datetime as dt
import secrets

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone
from django.utils.translation import gettext as _

from apps.core import ratelimit
from apps.core.clock import business_night, night_start
from apps.whispers.models import Whisper
from apps.whispers.services import whisper_service

from ..models import Booking

CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


class BookingError(Exception):
    """User-safe message."""


def _new_reference():
    return "B" + "".join(secrets.choice(CODE_ALPHABET) for _ in range(6))


def _queue_notice(booking_id: int, event: str):
    from apps.notifications.tasks import notify_booking

    transaction.on_commit(lambda: notify_booking.delay(booking_id, event))


def _describe(booking) -> str:
    return _("%(night)s at %(slot)s, %(guests)d guests, %(area)s") % {
        "night": booking.night.strftime("%a %d %b %Y"),
        "slot": booking.time_slot,
        "guests": booking.guests,
        "area": booking.get_area_display(),
    }


def request_booking(member, *, night: dt.date, time_slot: str, area: str, guests: int, note: str = "") -> Booking:
    from apps.accounts.models import Member

    starts_at = night_start(night, dt.time.fromisoformat(time_slot))
    now = timezone.now()
    if starts_at <= now:
        raise BookingError(_("Please choose a time that has not passed yet."))
    if night > business_night(now) + dt.timedelta(days=settings.BOOKING_MAX_DAYS_AHEAD):
        raise BookingError(_("Bookings open %(days)d days ahead.") % {"days": settings.BOOKING_MAX_DAYS_AHEAD})
    if not 1 <= guests <= settings.BOOKING_MAX_GUESTS:
        raise BookingError(_("Guests must be between 1 and %(max)d.") % {"max": settings.BOOKING_MAX_GUESTS})
    if ratelimit.hit("booking", member.pk, 3600) > settings.BOOKING_REQUESTS_PER_HOUR:
        raise BookingError(_("Too many requests. Please try again in an hour."))

    with transaction.atomic():
        # Lock the member row so two quick requests cannot both pass the limit.
        Member.objects.select_for_update().only("pk").get(pk=member.pk)
        open_count = Booking.objects.filter(member=member, status__in=Booking.OPEN_STATUSES, starts_at__gt=now).count()
        if open_count >= settings.BOOKING_MAX_OPEN:
            raise BookingError(_("You can hold up to %(max)d upcoming bookings.") % {"max": settings.BOOKING_MAX_OPEN})
        try:
            with transaction.atomic():
                booking = Booking.objects.create(
                    reference=_new_reference(),
                    member=member,
                    night=night,
                    time_slot=time_slot,
                    starts_at=starts_at,
                    area=area,
                    guests=guests,
                    note=note.strip()[:300],
                )
        except IntegrityError as exc:
            raise BookingError(_("You already have a booking for that night.")) from exc
        whisper_service.send(
            member,
            _("Booking request received"),
            _("%(details)s. We will confirm shortly.") % {"details": _describe(booking)},
            kind=Whisper.Kind.BOOKING,
        )
        _queue_notice(booking.pk, "requested")
    return booking


def _locked(booking) -> Booking:
    return Booking.objects.select_for_update().select_related("member").get(pk=booking.pk)


def cancel(booking, member) -> Booking:
    with transaction.atomic():
        booking = _locked(booking)
        if booking.member_id != member.pk:
            raise BookingError(_("Booking not found."))
        if not booking.is_open or booking.starts_at <= timezone.now():
            raise BookingError(_("This booking can no longer be cancelled."))
        was_confirmed = booking.status == Booking.Status.CONFIRMED
        booking.status = Booking.Status.CANCELLED
        booking.save(update_fields=["status"])
        if was_confirmed:
            _queue_notice(booking.pk, "cancelled")
    return booking


def confirm(booking, staff, note: str = "") -> Booking:
    with transaction.atomic():
        booking = _locked(booking)
        if booking.status != Booking.Status.REQUESTED:
            raise BookingError(_("Only a new request can be confirmed."))
        booking.status = Booking.Status.CONFIRMED
        booking.staff_note = note.strip()[:300]
        booking.handled_by = staff
        booking.handled_at = timezone.now()
        booking.save(update_fields=["status", "staff_note", "handled_by", "handled_at"])
        body = _describe(booking)
        if booking.staff_note:
            body = f"{body}. {booking.staff_note}"
        whisper_service.send(booking.member, _("Your booking is confirmed"), body, kind=Whisper.Kind.BOOKING)
    return booking


def decline(booking, staff, note: str) -> Booking:
    if not note.strip():
        raise BookingError(_("Please write a short message for the member."))
    with transaction.atomic():
        booking = _locked(booking)
        if not booking.is_open:
            raise BookingError(_("This booking is already closed."))
        booking.status = Booking.Status.DECLINED
        booking.staff_note = note.strip()[:300]
        booking.handled_by = staff
        booking.handled_at = timezone.now()
        booking.save(update_fields=["status", "staff_note", "handled_by", "handled_at"])
        whisper_service.send(
            booking.member,
            _("We could not confirm your booking"),
            f"{_describe(booking)}. {booking.staff_note}",
            kind=Whisper.Kind.BOOKING,
        )
    return booking
