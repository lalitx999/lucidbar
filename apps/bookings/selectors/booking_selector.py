from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone

from apps.core.clock import business_night

from ..models import Booking


def member_bookings(member, limit: int = 20):
    """Upcoming first (soonest at the top), then the most recent past ones."""
    now = timezone.now()
    base = Booking.objects.filter(member=member)
    upcoming = list(base.filter(starts_at__gt=now).order_by("starts_at")[:limit])
    past = list(base.filter(starts_at__lte=now).order_by("-starts_at")[: max(0, limit - len(upcoming))])
    return upcoming, past


def member_booking_or_404(member, reference: str) -> Booking:
    return get_object_or_404(Booking, member=member, reference=reference)


def requests_queue(limit: int = 100):
    return (
        Booking.objects.filter(status=Booking.Status.REQUESTED, starts_at__gt=timezone.now())
        .select_related("member")
        .order_by("starts_at")[:limit]
    )


def upcoming_confirmed(limit: int = 100):
    return (
        Booking.objects.filter(status=Booking.Status.CONFIRMED, night__gte=business_night())
        .select_related("member", "handled_by")
        .order_by("starts_at")[:limit]
    )


def search(query: str, limit: int = 50):
    query = query.strip()
    if not query:
        return Booking.objects.none()
    return (
        Booking.objects.filter(
            Q(reference__iexact=query)
            | Q(member__email__icontains=query)
            | Q(member__full_name__icontains=query)
            | Q(member__handle__icontains=query)
        )
        .select_related("member", "handled_by")
        .order_by("-starts_at")[:limit]
    )


def booking_or_404(booking_id: int) -> Booking:
    return get_object_or_404(Booking.objects.select_related("member"), pk=booking_id)


def tonight_for_member(member):
    """The member's open booking for the current club night, if any (shown at the door)."""
    return (
        Booking.objects.filter(member=member, night=business_night(), status__in=Booking.OPEN_STATUSES)
        .order_by("starts_at")
        .first()
    )
