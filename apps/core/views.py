from django.db import connection
from django.http import HttpResponse, HttpResponsePermanentRedirect, JsonResponse
from django.shortcuts import redirect, render
from django.template.loader import render_to_string
from django.templatetags.static import static
from django.urls import reverse
from django.views.decorators.cache import cache_control, never_cache
from django.views.decorators.http import require_safe

from apps.keys.selectors import keys_selector
from apps.memberships.selectors import membership_selector
from apps.payments.selectors import payment_selector
from apps.treasures.selectors import treasure_selector

from . import pwa
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
    Member home: keys balance, seal, featured treasure. The Reveal status
    is added in Phase 4.
    """
    context = {
        "active_tab": "portal",
        "membership": membership_selector.current_membership(request.user),
        "open_intent": payment_selector.open_intent(request.user),
        "balance": keys_selector.balance_of(request.user),
        "featured": treasure_selector.featured(),
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
    return HttpResponsePermanentRedirect(static("img/pwa/favicon-32.png"))


# ---------------------------------------------------------------------------
# PWA
# ---------------------------------------------------------------------------
@require_safe
@cache_control(public=True, max_age=3600)
def web_manifest(request):
    response = JsonResponse(pwa.manifest(), json_dumps_params={"ensure_ascii": False})
    response["Content-Type"] = "application/manifest+json"
    return response


@require_safe
def service_worker(request):
    """
    Served from the site root so its scope covers every page. Browsers must
    always revalidate it, otherwise a deploy would not reach installed apps.
    """
    urls = pwa.precache_urls()
    body = render_to_string(
        "pwa/sw.js",
        {
            "version": pwa.cache_version(urls),
            "precache": urls,
            "offline_url": reverse("core:offline"),
            "static_prefix": static(""),
        },
    )
    response = HttpResponse(body, content_type="application/javascript; charset=utf-8")
    response["Cache-Control"] = "no-cache"
    response["Service-Worker-Allowed"] = "/"
    return response


@require_safe
@cache_control(public=True, max_age=3600)
def offline(request):
    """Shown by the service worker when there is no connection. No personal data."""
    return render(request, "core/offline.html")
