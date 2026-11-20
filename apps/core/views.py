from django.db import connection
from django.http import HttpResponsePermanentRedirect, JsonResponse
from django.shortcuts import redirect, render
from django.templatetags.static import static
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_safe

from apps.memberships.selectors import membership_selector
from apps.payments.selectors import payment_selector

from .decorators import member_required


@require_safe
def welcome(request):
    """Public landing page (first screen of the onboarding flow)."""
    if request.user.is_authenticated and request.user.is_verified:
        return redirect("core:portal")
    return render(request, "core/welcome.html")


@never_cache
@member_required
@require_safe
def portal(request):
    """
    Member home. Keys balance, featured treasure and the Reveal status are
    added here as their apps arrive (Phases 3-4).
    """
    context = {
        "active_tab": "portal",
        "membership": membership_selector.current_membership(request.user),
        "open_intent": payment_selector.open_intent(request.user),
    }
    return render(request, "portal/home.html", context)


@never_cache
@require_safe
def healthz(request):
    """
    Liveness and database check for Docker / the load balancer.

    Returns 503 when the database is unreachable so the container is marked
    unhealthy. No internal error details are exposed.
    """
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        return JsonResponse({"status": "ok"})
    except Exception:
        return JsonResponse({"status": "unavailable"}, status=503)


@require_safe
def favicon(request):
    """Browsers request /favicon.ico directly. Resolved per request so the
    hashed static file name from collectstatic is used in production."""
    return HttpResponsePermanentRedirect(static("img/logo-256.png"))
