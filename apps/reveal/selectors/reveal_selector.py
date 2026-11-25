from django.shortcuts import get_object_or_404

from ..models import ChosenDraw, WheelPrize, WheelSpin
from ..services.reveal_service import epoch_number_for


def wheel_prizes():
    return list(WheelPrize.objects.filter(is_active=True).order_by("sort_order", "pk"))


def current_draw():
    from django.utils import timezone

    return (
        ChosenDraw.objects.select_related("epoch", "winner")
        .filter(epoch__number=epoch_number_for(timezone.now()))
        .first()
    )


def can_spin(member) -> bool:
    """True if the member is this week's Chosen and has not spun yet. One query."""
    from django.utils import timezone

    return ChosenDraw.objects.filter(
        epoch__number=epoch_number_for(timezone.now()), winner=member, spin__isnull=True
    ).exists()


def member_spins(member, limit=10):
    return WheelSpin.objects.filter(member=member).select_related("prize", "draw__epoch")[:limit]


def recent_draws(limit=12):
    return ChosenDraw.objects.select_related("epoch", "winner", "drawn_by", "spin__prize").order_by("-epoch__number")[
        :limit
    ]


def ready_prizes(query: str = ""):
    qs = WheelSpin.objects.filter(status=WheelSpin.Status.READY).select_related("member", "prize", "draw__epoch")
    query = query.strip()
    if query:
        qs = qs.filter(claim_code__iexact=query) | qs.filter(member__email__icontains=query)
    return qs.order_by("created_at")


def spin_or_404(spin_id: int) -> WheelSpin:
    return get_object_or_404(WheelSpin.objects.select_related("member", "prize"), pk=spin_id)
