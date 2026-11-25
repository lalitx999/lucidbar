"""
Logging handler that tells the staff Telegram chat about server errors.

Only the exception type, a short message, the request method and path (no
query string, no user data) are sent. Identical errors are reported once per
ERROR_ALERT_COOLDOWN_SECONDS, and the handler never raises: a broken alert
must not break the request that failed.
"""

import hashlib
import logging

from django.conf import settings
from django.core.cache import cache

SKIP_LOGGERS = ("celery", "apps.notifications", "django.security.DisallowedHost")


class TelegramErrorHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        try:
            if not settings.TELEGRAM_BOT_TOKEN or record.name.startswith(SKIP_LOGGERS):
                return
            summary = self.summarise(record)
            fingerprint = hashlib.sha256(summary.encode()).hexdigest()[:16]
            if not cache.add(f"err-alert:{fingerprint}", 1, timeout=settings.ERROR_ALERT_COOLDOWN_SECONDS):
                return
            from .tasks import notify_error

            notify_error.apply_async(args=[summary], retry=False)
        except Exception:  # noqa: BLE001, S110 - alerts are best effort
            pass

    @staticmethod
    def summarise(record: logging.LogRecord) -> str:
        parts = [f"{record.levelname} in {record.name}"]
        request = getattr(record, "request", None)
        if request is not None and hasattr(request, "path"):
            parts.append(f"{request.method} {request.path[:200]}")
        if record.exc_info and record.exc_info[0]:
            exc_type, exc, _ = record.exc_info
            parts.append(f"{exc_type.__name__}: {str(exc)[:200]}")
        else:
            parts.append(record.getMessage()[:200])
        return "\n".join(parts)
