"""
Custom staff dashboard (not Django Admin). Every view is guarded by
@staff_required. Sections: payment review, treasure hand-over.
"""

from django.contrib import messages
from django.http import FileResponse
from django.shortcuts import redirect, render
from django.utils.translation import gettext as _
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST, require_safe

from apps.core.decorators import staff_required
from apps.payments.forms import StaffApproveForm, StaffRejectForm
from apps.payments.selectors import payment_selector
from apps.payments.services import payment_service
from apps.treasures.selectors import treasure_selector
from apps.treasures.services import redemption_service


@never_cache
@staff_required
@require_safe
def home(request):
    return redirect("dashboard:payments")


@never_cache
@staff_required
@require_safe
def payments(request):
    context = {
        "queue": payment_selector.review_queue(),
        "recent": payment_selector.recent_decided(),
        "section": "payments",
    }
    return render(request, "dashboard/payments.html", context)


@never_cache
@staff_required
@require_safe
def payment_detail(request, reference):
    context = {
        "intent": payment_selector.staff_intent_or_404(reference),
        "approve_form": StaffApproveForm(),
        "reject_form": StaffRejectForm(),
        "section": "payments",
    }
    return render(request, "dashboard/payment_detail.html", context)


@staff_required
@require_POST
def payment_approve(request, reference):
    intent = payment_selector.staff_intent_or_404(reference)
    form = StaffApproveForm(request.POST)
    if form.is_valid():
        try:
            payment_service.staff_approve(intent, request.user, form.cleaned_data["trans_ref"])
        except payment_service.PaymentError as exc:
            messages.error(request, str(exc))
            return redirect("dashboard:payment_detail", reference=reference)
        messages.success(request, _("Payment %(ref)s approved.") % {"ref": reference})
    return redirect("dashboard:payments")


@staff_required
@require_POST
def payment_reject(request, reference):
    intent = payment_selector.staff_intent_or_404(reference)
    form = StaffRejectForm(request.POST)
    if not form.is_valid():
        messages.error(request, _("Please write a short message for the member."))
        return redirect("dashboard:payment_detail", reference=reference)
    try:
        payment_service.staff_reject(
            intent, request.user, form.cleaned_data["reason"], form.cleaned_data["allow_new_slip"]
        )
    except payment_service.PaymentError as exc:
        messages.error(request, str(exc))
        return redirect("dashboard:payment_detail", reference=reference)
    messages.success(request, _("Payment %(ref)s rejected.") % {"ref": reference})
    return redirect("dashboard:payments")


@never_cache
@staff_required
@require_safe
def slip_image(request, slip_id):
    """Stream a private slip image to staff. Never cached by browsers or proxies."""
    slip = payment_selector.slip_or_404(slip_id)
    response = FileResponse(slip.image.open("rb"), content_type="image/jpeg")
    response["Cache-Control"] = "private, no-store"
    response["X-Content-Type-Options"] = "nosniff"
    return response


# ---------------------------------------------------------------------------
# Treasure hand-over
# ---------------------------------------------------------------------------
@never_cache
@staff_required
@require_safe
def redemptions(request):
    query = request.GET.get("q", "")
    context = {
        "query": query,
        "ready": treasure_selector.ready_redemptions(query),
        "recent": treasure_selector.recent_handled(),
        "section": "redemptions",
    }
    return render(request, "dashboard/redemptions.html", context)


@staff_required
@require_POST
def redemption_hand_over(request, redemption_id):
    redemption = treasure_selector.redemption_or_404(redemption_id)
    try:
        redemption_service.hand_over(redemption, request.user)
    except redemption_service.RedemptionError as exc:
        messages.error(request, str(exc))
    else:
        messages.success(
            request,
            _("%(item)s handed over to %(name)s.")
            % {"item": redemption.treasure.name, "name": redemption.member.full_name},
        )
    return redirect("dashboard:redemptions")


@staff_required
@require_POST
def redemption_cancel(request, redemption_id):
    redemption = treasure_selector.redemption_or_404(redemption_id)
    try:
        redemption_service.cancel(redemption, request.user)
    except redemption_service.RedemptionError as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, _("Cancelled and %(keys)d keys refunded.") % {"keys": redemption.keys_spent})
    return redirect("dashboard:redemptions")
