from django.contrib import messages
from django.shortcuts import redirect, render
from django.utils.translation import gettext as _
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST, require_safe

from apps.core.decorators import member_required
from apps.keys.selectors import keys_selector

from .selectors import treasure_selector
from .services import redemption_service


@never_cache
@member_required
@require_safe
def catalog(request):
    treasures = list(treasure_selector.catalog())
    context = {
        "balance": keys_selector.balance_of(request.user),
        "featured": next((t for t in treasures if t.is_featured), None),
        "treasures": treasures,
        "redemptions": treasure_selector.member_redemptions(request.user),
        "active_tab": "treasures",
    }
    return render(request, "treasures/catalog.html", context)


@never_cache
@member_required
@require_safe
def detail(request, treasure_id):
    """Confirmation screen before keys are spent (no JavaScript needed)."""
    treasure = treasure_selector.active_treasure_or_404(treasure_id)
    balance = keys_selector.balance_of(request.user)
    context = {
        "treasure": treasure,
        "balance": balance,
        "missing": max(treasure.keys_cost - balance, 0),
        "active_tab": "treasures",
    }
    return render(request, "treasures/detail.html", context)


@member_required
@require_POST
def unlock(request, treasure_id):
    try:
        redemption = redemption_service.redeem(request.user, treasure_id)
    except redemption_service.RedemptionError as exc:
        messages.error(request, str(exc))
        return redirect("treasures:detail", treasure_id=treasure_id)
    messages.success(
        request,
        _("Unlocked. Show code %(code)s to our staff to collect it.") % {"code": redemption.claim_code},
    )
    return redirect("treasures:catalog")
