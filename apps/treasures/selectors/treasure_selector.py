from django.db.models import Q
from django.shortcuts import get_object_or_404

from ..models import Redemption, Treasure

CATALOG_FIELDS = ("name", "category", "description", "image", "keys_cost", "stock", "is_featured")


def catalog():
    return Treasure.objects.filter(is_active=True).only(*CATALOG_FIELDS)


def featured():
    return Treasure.objects.filter(is_active=True, is_featured=True).only(*CATALOG_FIELDS).first()


def active_treasure_or_404(treasure_id: int) -> Treasure:
    return get_object_or_404(Treasure, pk=treasure_id, is_active=True)


def member_redemptions(member, limit=20):
    return Redemption.objects.filter(member=member).select_related("treasure")[:limit]


def ready_redemptions(query: str = ""):
    """Staff hand-over list. Search by claim code, member email, name or handle."""
    qs = Redemption.objects.filter(status=Redemption.Status.READY).select_related("member", "treasure")
    query = query.strip()
    if query:
        qs = qs.filter(
            Q(claim_code__iexact=query)
            | Q(member__email__icontains=query)
            | Q(member__full_name__icontains=query)
            | Q(member__handle__icontains=query)
        )
    return qs.order_by("created_at")


def recent_handled(limit=20):
    return (
        Redemption.objects.exclude(status=Redemption.Status.READY)
        .select_related("member", "treasure", "handled_by")
        .order_by("-handled_at")[:limit]
    )


def redemption_or_404(redemption_id: int) -> Redemption:
    return get_object_or_404(Redemption.objects.select_related("member", "treasure"), pk=redemption_id)
