"""Read-only queries for the manager pages."""

from apps.bookings.models import Booking
from apps.checkin.models import CheckIn
from apps.keys.models import Spending
from apps.memberships.models import Membership, SealTier
from apps.reveal.models import WheelPrize
from apps.treasures.models import Treasure


def member_activity(member) -> dict:
    return {
        "memberships": Membership.objects.filter(member=member).select_related("tier").order_by("-starts_at")[:10],
        "visits": CheckIn.objects.filter(member=member).select_related("created_by").order_by("-night")[:10],
        "bookings": Booking.objects.filter(member=member).order_by("-starts_at")[:10],
        "spendings": Spending.objects.filter(member=member).select_related("recorded_by")[:10],
    }


def all_tiers():
    return SealTier.objects.order_by("sort_order")


def tier_or_404(tier_id):
    from django.shortcuts import get_object_or_404

    return get_object_or_404(SealTier, pk=tier_id)


def prizes_with_chance():
    rows = list(WheelPrize.objects.order_by("sort_order", "pk"))
    total = sum(p.weight for p in rows if p.is_active) or 1
    for p in rows:
        p.chance = round(100 * p.weight / total, 1) if p.is_active else 0
    return rows


def prize_or_404(prize_id):
    from django.shortcuts import get_object_or_404

    return get_object_or_404(WheelPrize, pk=prize_id)


def catalog():
    return Treasure.objects.order_by("-is_active", "sort_order", "keys_cost", "name")


def treasure_or_404(treasure_id):
    from django.shortcuts import get_object_or_404

    return get_object_or_404(Treasure, pk=treasure_id)
