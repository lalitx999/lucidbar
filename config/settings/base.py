"""
Base settings shared by every environment.

Secrets and anything that differs between machines come from environment
variables (loaded from `.env` by django-environ). Nothing secret is hardcoded.
"""

from pathlib import Path

import environ
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env()
# Read .env if present. Real environment variables always win over the file.
environ.Env.read_env(BASE_DIR / ".env", overwrite=False)

SECRET_KEY = env("DJANGO_SECRET_KEY")
DEBUG = False
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS", default=[])

# ---------------------------------------------------------------------------
# Applications
# ---------------------------------------------------------------------------
DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]

LOCAL_APPS = [
    "apps.core",
    "apps.accounts",
    "apps.notifications",
    "apps.memberships",
    "apps.payments",
    "apps.keys",
    "apps.treasures",
    "apps.dashboard",
]

INSTALLED_APPS = DJANGO_APPS + LOCAL_APPS

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "apps.core.middleware.ContentSecurityPolicyMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "apps.core.context_processors.site",
            ],
        },
    },
]

# ---------------------------------------------------------------------------
# Database (PostgreSQL only)
# ---------------------------------------------------------------------------
DATABASES = {
    "default": env.db("DATABASE_URL"),
}
DATABASES["default"]["CONN_MAX_AGE"] = env.int("DB_CONN_MAX_AGE", default=60)
DATABASES["default"]["CONN_HEALTH_CHECKS"] = True
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ---------------------------------------------------------------------------
# Cache (Redis). Also used later for login and OTP rate limiting.
# ---------------------------------------------------------------------------
REDIS_URL = env("REDIS_URL", default="redis://localhost:6379/0")
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": REDIS_URL,
    }
}

# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------
AUTH_USER_MODEL = "accounts.Member"
LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "core:portal"
LOGOUT_REDIRECT_URL = "core:welcome"

# Email OTP rules
OTP_LENGTH = 6
OTP_TTL_SECONDS = env.int("OTP_TTL_SECONDS", default=10 * 60)
OTP_MAX_ATTEMPTS = 5
OTP_MAX_SENDS = 3  # per email address per OTP_SEND_WINDOW_SECONDS
OTP_SEND_WINDOW_SECONDS = 15 * 60

# Login throttling (per email and per IP)
LOGIN_MAX_FAILURES = 5
LOGIN_LOCKOUT_SECONDS = 15 * 60

# Trust the X-Real-IP header (set by our Nginx). Only enable behind the proxy.
TRUST_X_REAL_IP = False

# Membership rules
MINIMUM_AGE = 20

SESSION_COOKIE_AGE = 60 * 60 * 24 * 14
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 10}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ---------------------------------------------------------------------------
# Internationalisation: English first, every string wrapped for Thai later.
# ---------------------------------------------------------------------------
LANGUAGE_CODE = "en"
LANGUAGES = [
    ("en", "English"),
]
LOCALE_PATHS = [BASE_DIR / "locale"]
TIME_ZONE = "Asia/Bangkok"
USE_I18N = True
USE_TZ = True

# ---------------------------------------------------------------------------
# Static and media
# ---------------------------------------------------------------------------
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
MEDIA_ROOT = env.path("MEDIA_ROOT", default=BASE_DIR / "media")
MEDIA_URL = "/media/"

# Private uploads (payment slips). This folder has no URL and is never served
# by Nginx; files are only streamed through permission-checked views.
PRIVATE_MEDIA_ROOT = env.path("PRIVATE_MEDIA_ROOT", default=BASE_DIR / "private")

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "private": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
        "OPTIONS": {"location": PRIVATE_MEDIA_ROOT, "base_url": None},
    },
    # Hashed file names give safe long-term caching for the PWA service worker.
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

# ---------------------------------------------------------------------------
# Celery (email, Telegram and EasySlip run here, never in the request cycle)
# ---------------------------------------------------------------------------
CELERY_BROKER_URL = env("CELERY_BROKER_URL", default=REDIS_URL)
CELERY_RESULT_BACKEND = None
CELERY_TASK_ACKS_LATE = True
CELERY_TASK_REJECT_ON_WORKER_LOST = True
CELERY_WORKER_PREFETCH_MULTIPLIER = 1
CELERY_TASK_TIME_LIMIT = 120
CELERY_TASK_SOFT_TIME_LIMIT = 90
CELERY_TIMEZONE = TIME_ZONE

# ---------------------------------------------------------------------------
# Email (Hostinger SMTP)
# ---------------------------------------------------------------------------
EMAIL_BACKEND = env("EMAIL_BACKEND", default="") or "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = env("EMAIL_HOST", default="smtp.hostinger.com")
EMAIL_PORT = env.int("EMAIL_PORT", default=465)
EMAIL_USE_SSL = env.bool("EMAIL_USE_SSL", default=True)
EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", default=False)
EMAIL_HOST_USER = env("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="")
EMAIL_TIMEOUT = 20
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="Lucid Society <no-reply@localhost>")
SERVER_EMAIL = DEFAULT_FROM_EMAIL

# ---------------------------------------------------------------------------
# Security defaults (tightened further in production.py)
# ---------------------------------------------------------------------------
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"
X_FRAME_OPTIONS = "DENY"
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"

# Content-Security-Policy: everything from our own origin only (no CDN).
CSP_POLICY = (
    "default-src 'self'; "
    "img-src 'self' data:; "
    "style-src 'self'; "
    "script-src 'self'; "
    "font-src 'self'; "
    "connect-src 'self'; "
    "manifest-src 'self'; "
    "worker-src 'self'; "
    "frame-ancestors 'none'; "
    "base-uri 'self'; "
    "form-action 'self'"
)

# ---------------------------------------------------------------------------
# Logging: everything to stdout so Docker collects it.
# ---------------------------------------------------------------------------
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "plain": {"format": "%(asctime)s %(levelname)s %(name)s %(message)s"},
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "plain"},
    },
    "root": {"handlers": ["console"], "level": "INFO"},
}

# ---------------------------------------------------------------------------
# Site settings exposed to templates
# ---------------------------------------------------------------------------
SITE_NAME = "Lucid Society"
SITE_TAGLINE = "See beyond the illusion"

# ---------------------------------------------------------------------------
# Payments
# ---------------------------------------------------------------------------
# Where members send money. Shown on the Pay screen and used to check slips.
PAYMENT_BANK_NAME = env("PAYMENT_BANK_NAME", default="")
PAYMENT_BANK_ACCOUNT_NUMBER = env("PAYMENT_BANK_ACCOUNT_NUMBER", default="")
PAYMENT_BANK_ACCOUNT_NAME = env("PAYMENT_BANK_ACCOUNT_NAME", default="")
# Optional PromptPay ID (mobile number or 13-digit tax ID). When set, the Pay
# screen shows a QR with the exact amount; otherwise the static club poster.
PROMPTPAY_ID = env("PROMPTPAY_ID", default="")

PAYMENT_INTENT_TTL_HOURS = 24
SLIP_MAX_BYTES = 4 * 1024 * 1024  # EasySlip limit is 4 MB
SLIP_MAX_UPLOADS_PER_INTENT = 5
# A slip dated earlier than this before checkout started is sent to staff review.
SLIP_DATE_GRACE_MINUTES = 30

# EasySlip v2. Modes: "live" (real API), "off" (every slip goes to staff
# review), "fake" (auto-approve, local development only; refused in production).
EASYSLIP_API_KEY = env("EASYSLIP_API_KEY", default="")
EASYSLIP_MODE = env("EASYSLIP_MODE", default="") or ("live" if EASYSLIP_API_KEY else "off")
if EASYSLIP_MODE not in {"live", "off", "fake"}:
    raise ImproperlyConfigured(f"EASYSLIP_MODE must be live, off or fake (got {EASYSLIP_MODE!r})")
EASYSLIP_URL = "https://api.easyslip.com/v2/verify/bank"
EASYSLIP_TIMEOUT_SECONDS = 20

# Telegram alerts to the staff group. Empty token disables sending.
TELEGRAM_BOT_TOKEN = env("TELEGRAM_BOT_TOKEN", default="")
TELEGRAM_CHAT_ID = env("TELEGRAM_CHAT_ID", default="")
TELEGRAM_TIMEOUT_SECONDS = 15

# Django Admin path (superuser only). Set a hard-to-guess value in production.
ADMIN_URL = env("DJANGO_ADMIN_URL", default="admin/")
