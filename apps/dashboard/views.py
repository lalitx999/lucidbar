"""
Custom staff dashboard (not Django Admin). Every view is guarded by
@staff_required (or @manager_required for manager-only actions).
Sections: door check-in, bookings, payments, treasure hand-over, the Reveal,
broadcasts.
"""

from django.contrib import messages
from django.http import FileResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.formats import date_format
from django.utils.timezone import localtime
from django.utils.translation import gettext as _
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods, require_POST, require_safe

from apps.bookings.forms import StaffConfirmForm, StaffDeclineForm
from apps.bookings.selectors import booking_selector
from apps.bookings.services import booking_service
from apps.checkin.selectors import checkin_selector
from apps.checkin.services import checkin_service
from apps.core.decorators import is_manager, manager_required, staff_required
from apps.memberships.selectors import membership_selector
from apps.payments.forms import StaffApproveForm, StaffRejectForm
from apps.payments.selectors import payment_selector
from apps.payments.services import payment_service
from apps.reveal.selectors import reveal_selector
from apps.reveal.services import reveal_service
from apps.treasures.selectors import treasure_selector
from apps.treasures.services import redemption_service
from apps.whispers.forms import BroadcastForm
from apps.whispers.selectors import whisper_selector
from apps.whispers.services import whisper_service


@never_cache
@staff_required
@require_safe
def home(request):
    return redirect("dashboard:door")


# ---------------------------------------------------------------------------
# Door check-in
# ---------------------------------------------------------------------------
@never_cache
@staff_required
@require_safe
def door(request):
    last = checkin_selector.checkin_or_none(request.GET.get("last"))
    context = {
        "last": last,
        "last_membership": membership_selector.current_membership(last.member) if last else None,
        "last_booking": booking_selector.tonight_for_member(last.member) if last else None,
        "tonight": checkin_selector.tonight(),
        "section": "door",
    }
    return render(request, "dashboard/door.html", context)


@staff_required
@require_POST
def door_scan(request):
    try:
        result = checkin_service.check_in_with_card(request.POST.get("token", ""), request.user)
    except checkin_service.CheckInError as exc:
        messages.error(request, str(exc))
        return redirect("dashboard:door")
    checkin = result.checkin
    if result.created:
        messages.success(
            request,
            _("%(name)s checked in. %(keys)d keys awarded.")
            % {"name": checkin.member.full_name, "keys": checkin.keys_awarded},
        )
    else:
        messages.warning(
            request,
            _("%(name)s already checked in tonight at %(time)s. No keys awarded.")
            % {"name": checkin.member.full_name, "time": date_format(localtime(checkin.created_at), "H:i")},
        )
    return redirect(f"{reverse('dashboard:door')}?last={checkin.pk}")


# ---------------------------------------------------------------------------
# VIP Chamber bookings
# ---------------------------------------------------------------------------
@never_cache
@staff_required
@require_safe
def bookings(request):
    query = request.GET.get("q", "")
    context = {
        "query": query,
        "results": booking_selector.search(query),
        "requests": booking_selector.requests_queue(),
        "confirmed": booking_selector.upcoming_confirmed(),
        "section": "bookings",
    }
    return render(request, "dashboard/bookings.html", context)


@staff_required
@require_POST
def booking_confirm(request, booking_id):
    booking = booking_selector.booking_or_404(booking_id)
    form = StaffConfirmForm(request.POST)
    note = form.cleaned_data["note"] if form.is_valid() else ""
    try:
        booking_service.confirm(booking, request.user, note)
    except booking_service.BookingError as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, _("Booking %(ref)s confirmed.") % {"ref": booking.reference})
    return redirect("dashboard:bookings")


@staff_required
@require_POST
def booking_decline(request, booking_id):
    booking = booking_selector.booking_or_404(booking_id)
    form = StaffDeclineForm(request.POST)
    if not form.is_valid():
        messages.error(request, _("Please write a short message for the member."))
        return redirect("dashboard:bookings")
    try:
        booking_service.decline(booking, request.user, form.cleaned_data["note"])
    except booking_service.BookingError as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, _("Booking %(ref)s declined.") % {"ref": booking.reference})
    return redirect("dashboard:bookings")


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


# ---------------------------------------------------------------------------
# The Reveal
# ---------------------------------------------------------------------------
@never_cache
@staff_required
@require_safe
def reveal(request):
    query = request.GET.get("q", "")
    context = {
        "epoch": reveal_service.current_epoch(),
        "draw": reveal_selector.current_draw(),
        "eligible_count": len(reveal_service.eligible_member_ids()),
        "history": reveal_selector.recent_draws(),
        "prizes_ready": reveal_selector.ready_prizes(query),
        "query": query,
        "can_draw": is_manager(request.user),
        "section": "reveal",
    }
    return render(request, "dashboard/reveal.html", context)


@manager_required
@require_POST
def reveal_draw(request):
    try:
        draw = reveal_service.run_draw(request.user)
    except reveal_service.RevealError as exc:
        messages.error(request, str(exc))
    else:
        messages.success(
            request,
            _("%(name)s is this week's Chosen (from %(count)d eligible members).")
            % {"name": draw.winner.full_name, "count": draw.eligible_count},
        )
    return redirect("dashboard:reveal")


@staff_required
@require_POST
def prize_hand_over(request, spin_id):
    wheel_spin = reveal_selector.spin_or_404(spin_id)
    try:
        reveal_service.hand_over_prize(wheel_spin, request.user)
    except reveal_service.RevealError as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, _("%(prize)s handed over.") % {"prize": wheel_spin.prize.label})
    return redirect("dashboard:reveal")


# ---------------------------------------------------------------------------
# Broadcast whispers
# ---------------------------------------------------------------------------
@never_cache
@manager_required
@require_http_methods(["GET", "POST"])
def broadcasts(request):
    form = BroadcastForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        whisper_service.create_broadcast(
            form.cleaned_data["title"], form.cleaned_data["body"], form.cleaned_data["audience"], request.user
        )
        messages.success(request, _("Broadcast queued. Members will see it in their Whispers."))
        return redirect("dashboard:broadcasts")
    context = {"form": form, "recent": whisper_selector.recent_broadcasts(), "section": "broadcasts"}
    return render(request, "dashboard/broadcasts.html", context)
