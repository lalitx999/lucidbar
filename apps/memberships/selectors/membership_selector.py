from django.db.models import Q
from django.utils import timezone

from ..models import Membership, SealTier


def active_memberships(member, at=None):
    at = at or timezone.now()
    return (
        Membership.objects.filter(member=member, starts_at__lte=at)
        .filter(Q(ends_at__isnull=True) | Q(ends_at__gt=at))
        .select_related("tier")
    )


def current_membership(member, at=None) -> Membership | None:
    """The best tier the member holds right now (highest sort_order)."""
    return active_memberships(member, at).order_by("-tier__sort_order", "-ends_at").first()


def latest_paid_end(member, tier, at=None):
    """End of the member's furthest active paid period for this tier, if any."""
    at = at or timezone.now()
    row = (
        Membership.objects.filter(member=member, tier=tier, ends_at__gt=at)
        .order_by("-ends_at")
        .values_list("ends_at", flat=True)
        .first()
    )
    return row


def purchasable_tiers():
    return SealTier.objects.filter(is_active=True, price_satang__gt=0).order_by("sort_order")


def all_active_tiers():
    return SealTier.objects.filter(is_active=True).order_by("sort_order")


def signup_tier() -> SealTier | None:
    """The free tier granted on email verification (lowest active free tier)."""
    return SealTier.objects.filter(is_active=True, price_satang=0).order_by("sort_order").first()
