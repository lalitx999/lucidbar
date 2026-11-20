"""
Minimal Telegram Bot API client for staff alerts. Call only from Celery tasks.

Messages use HTML parse mode, so every dynamic value must go through
html.escape() before it is placed in the text.
"""

import logging

import requests
from django.conf import settings

logger = logging.getLogger(__name__)
API = "https://api.telegram.org/bot{token}/{method}"


class TelegramTemporaryError(Exception):
    pass


def is_configured():
    return bool(settings.TELEGRAM_BOT_TOKEN and settings.TELEGRAM_CHAT_ID)


def _call(method, *, data, files=None):
    url = API.format(token=settings.TELEGRAM_BOT_TOKEN, method=method)
    try:
        response = requests.post(url, data=data, files=files, timeout=settings.TELEGRAM_TIMEOUT_SECONDS)
    except requests.RequestException as exc:
        raise TelegramTemporaryError(type(exc).__name__) from exc
    if response.status_code == 429 or response.status_code >= 500:
        raise TelegramTemporaryError(f"HTTP {response.status_code}")
    if response.status_code != 200:
        # Never log the URL: it contains the bot token.
        logger.error("Telegram %s failed with HTTP %s", method, response.status_code)
    return response.status_code == 200


def send_message(text: str) -> bool:
    if not is_configured():
        logger.info("Telegram not configured; message skipped")
        return False
    return _call(
        "sendMessage",
        data={"chat_id": settings.TELEGRAM_CHAT_ID, "text": text, "parse_mode": "HTML"},
    )


def send_photo(photo: bytes, caption: str) -> bool:
    if not is_configured():
        logger.info("Telegram not configured; photo skipped")
        return False
    return _call(
        "sendPhoto",
        data={"chat_id": settings.TELEGRAM_CHAT_ID, "caption": caption[:1024], "parse_mode": "HTML"},
        files={"photo": ("slip.jpg", photo, "image/jpeg")},
    )
