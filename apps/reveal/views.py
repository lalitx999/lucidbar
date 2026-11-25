from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils.translation import gettext as _
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST, require_safe

from apps.core.decorators import member_required

from . import wheel
from .selectors import reveal_selector
from .services import reveal_service


def _wants_json(request):
    return "application/json" in request.headers.get("Accept", "")


@never_cache
@member_required
@require_safe
def reveal_page(request):
    prizes = reveal_selector.wheel_prizes()
    draw = reveal_selector.current_draw()
    is_chosen = bool(draw and draw.winner_id == request.user.pk)
    spin = getattr(draw, "spin", None) if is_chosen else None
    context = {
        "epoch": reveal_service.current_epoch(),
        "draw": draw,
        "is_chosen": is_chosen,
        "spin": spin,
        "segments": wheel.segments([p.label for p in prizes]),
        "prizes": prizes,
        "past_spins": reveal_selector.member_spins(request.user),
        # A finished spin shows the wheel resting on the won segment.
        "resting_rotation": wheel.landing_rotation(spin.segment_index, len(prizes), 0) if spin and prizes else 0,
        "active_tab": "reveal",
    }
    return render(request, "reveal/reveal.html", context)


@member_required
@require_POST
def spin_wheel(request):
    """
    POST to spin. Returns JSON for the animated wheel, or redirects for the
    no-JavaScript fallback. The outcome is decided here, never in the browser.
    """
    try:
        result = reveal_service.spin(request.user)
    except reveal_service.RevealError as exc:
        if _wants_json(request):
            return JsonResponse({"ok": False, "message": str(exc)}, status=400)
        messages.error(request, str(exc))
        return redirect("reveal:reveal")

    count = len(reveal_selector.wheel_prizes())
    if _wants_json(request):
        return JsonResponse(
            {
                "ok": True,
                "segment": result.segment_index,
                "rotation": wheel.landing_rotation(result.segment_index, count),
                "prize": result.prize.label,
                "description": result.prize.description,
                "value": result.prize.value_text,
                "claim_code": result.claim_code,
            }
        )
    messages.success(request, _("You won %(prize)s.") % {"prize": result.prize.label})
    return redirect("reveal:reveal")
