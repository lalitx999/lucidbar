from django.conf import settings


def site(request):
    """Expose a few site-wide values to every template."""
    return {
        "SITE_NAME": settings.SITE_NAME,
        "SITE_TAGLINE": settings.SITE_TAGLINE,
    }
