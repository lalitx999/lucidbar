"""
Production settings (VPS behind Nginx with TLS).

DEBUG is always False. Nginx serves /static/ directly; WhiteNoise stays in the
middleware stack as a fallback.
"""

from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F403
from .base import env

DEBUG = False
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS")
CSRF_TRUSTED_ORIGINS = env.list("DJANGO_CSRF_TRUSTED_ORIGINS", default=[])

# Nginx terminates TLS and forwards the original scheme.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
TRUST_X_REAL_IP = True
SECURE_SSL_REDIRECT = env.bool("DJANGO_SECURE_SSL_REDIRECT", default=True)
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = env.int("DJANGO_HSTS_SECONDS", default=60 * 60 * 24 * 365)
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = False

LOGGING["root"]["level"] = env("DJANGO_LOG_LEVEL", default="INFO")  # noqa: F405
# Server errors also go to the staff Telegram chat (rate limited, no personal data).
LOGGING["handlers"]["telegram"] = {  # noqa: F405
    "class": "apps.notifications.logging.TelegramErrorHandler",
    "level": "ERROR",
}
LOGGING["root"]["handlers"] = ["console", "telegram"]  # noqa: F405

# HSTS preload is a long-term commitment for the whole domain; opt in deliberately later.
SILENCED_SYSTEM_CHECKS = ["security.W021"]

# Refuse to start with placeholder secrets or the default admin path.
if len(SECRET_KEY) < 40 or SECRET_KEY.startswith(("change-me", "django-insecure")):  # noqa: F405
    raise ImproperlyConfigured("Set a long random DJANGO_SECRET_KEY for production.")
if ADMIN_URL.strip("/") == "admin":  # noqa: F405
    raise ImproperlyConfigured("Set DJANGO_ADMIN_URL to a hard-to-guess path in production.")

# Fake slip approval is a local development aid only.
if EASYSLIP_MODE == "fake":  # noqa: F405
    raise ImproperlyConfigured("EASYSLIP_MODE=fake is not allowed in production.")
