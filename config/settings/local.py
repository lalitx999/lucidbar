"""Local development settings."""

from .base import *  # noqa: F403
from .base import env

DEBUG = True
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS", default=["localhost", "127.0.0.1", "0.0.0.0"])  # noqa: S104 (Docker port binding)

# Print emails to the console unless a real SMTP backend is configured in .env.
# An empty EMAIL_BACKEND in .env also falls back to the console.
EMAIL_BACKEND = env("EMAIL_BACKEND", default="") or "django.core.mail.backends.console.EmailBackend"

# Serve static files straight from STATICFILES_DIRS without collectstatic.
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}
WHITENOISE_USE_FINDERS = True
WHITENOISE_AUTOREFRESH = True

# Run Celery tasks in-process so OTP emails appear in the runserver console
# without a separate worker. Set CELERY_TASK_ALWAYS_EAGER=False to test a worker.
CELERY_TASK_ALWAYS_EAGER = env.bool("CELERY_TASK_ALWAYS_EAGER", default=True)
