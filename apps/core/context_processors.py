from django.conf import settings
from django.utils.functional import SimpleLazyObject


def site(request):
    """Expose a few site-wide values to every template."""
    return {
        "SITE_NAME": settings.SITE_NAME,
        "SITE_TAGLINE": settings.SITE_TAGLINE,
    }


def portal(request):
    """
    Badges for the member portal layout: unread whispers and whether the
    member may spin the wheel. Lazy, so pages that never show them run no
    extra queries.
    """
    user = getattr(request, "user", None)
    if not (user and user.is_authenticated and getattr(user, "is_verified", False)):
        return {}

    def unread():
        from apps.whispers.selectors import whisper_selector

        return whisper_selector.unread_count(user)

    def can_spin():
        from apps.reveal.selectors import reveal_selector

        return reveal_selector.can_spin(user)

    return {"unread_whispers": SimpleLazyObject(unread), "can_spin": SimpleLazyObject(can_spin)}
