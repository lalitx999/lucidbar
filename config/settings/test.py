"""Settings for the automated test suite."""

import os

# Defaults so the suite runs without a .env file. Real env vars still win.
os.environ.setdefault("DJANGO_SECRET_KEY", "test-only-secret-key-not-used-anywhere-else")
os.environ.setdefault("DATABASE_URL", "postgres://localhost:5432/lucid_test")

from .base import *  # noqa: E402, F403

DEBUG = False
ALLOWED_HOSTS = ["testserver", "localhost"]

# Fast hashing and in-memory backends keep tests quick and isolated.
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.InMemoryStorage"},
    "private": {"BACKEND": "django.core.files.storage.InMemoryStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}
WHITENOISE_USE_FINDERS = True
WHITENOISE_AUTOREFRESH = True

EASYSLIP_MODE = "live"
EASYSLIP_API_KEY = "test-key"
PAYMENT_BANK_NAME = "UOB"
PAYMENT_BANK_ACCOUNT_NUMBER = "7811737430"
PAYMENT_BANK_ACCOUNT_NAME = "Test Club Co., Ltd."
PROMPTPAY_ID = "0812345678"
TELEGRAM_BOT_TOKEN = ""
TELEGRAM_CHAT_ID = ""
