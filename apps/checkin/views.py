from django.http import HttpResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_safe

from apps.core import qr
from apps.core.decorators import member_required

from .services import card_service


@never_cache
@member_required
@require_safe
def card_qr(request):
    """A freshly signed QR identity card as SVG. Never cached anywhere."""
    svg = qr.render_svg(card_service.make_token(request.user), border=2)
    response = HttpResponse(svg, content_type="image/svg+xml")
    response["Cache-Control"] = "private, no-store"
    response["X-Content-Type-Options"] = "nosniff"
    return response
