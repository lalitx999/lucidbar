from django.contrib import messages
from django.shortcuts import redirect, render
from django.utils.translation import gettext as _
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods, require_POST

from apps.core.decorators import member_required

from .forms import BookingForm
from .selectors import booking_selector
from .services import booking_service


@never_cache
@member_required
@require_http_methods(["GET", "POST"])
def chamber(request):
    form = BookingForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            booking = booking_service.request_booking(request.user, **form.cleaned_data)
        except booking_service.BookingError as exc:
            form.add_error(None, str(exc))
        else:
            messages.success(
                request, _("Request %(ref)s sent. We will confirm it in your Whispers.") % {"ref": booking.reference}
            )
            return redirect("bookings:chamber")
    upcoming, past = booking_selector.member_bookings(request.user)
    context = {"form": form, "upcoming": upcoming, "past": past, "active_tab": "portal"}
    return render(request, "bookings/chamber.html", context)


@member_required
@require_POST
def cancel(request, reference):
    booking = booking_selector.member_booking_or_404(request.user, reference)
    try:
        booking_service.cancel(booking, request.user)
    except booking_service.BookingError as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, _("Booking %(ref)s cancelled.") % {"ref": reference})
    return redirect("bookings:chamber")
