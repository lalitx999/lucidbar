"""
Outbound notifications. Every send runs in a Celery worker, never in a request.

Email goes through Django's configured backend (Hostinger SMTP in production,
console in local development).
"""

import logging
import smtplib
import socket
from html import escape

from celery import shared_task
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string

from . import telegram
from .telegram import TelegramTemporaryError

logger = logging.getLogger(__name__)

# Network-level failures worth retrying. Bad addresses or auth errors are not.
RETRYABLE_ERRORS = (smtplib.SMTPServerDisconnected, smtplib.SMTPConnectError, socket.timeout, ConnectionError)


@shared_task(
    bind=True,
    autoretry_for=RETRYABLE_ERRORS,
    retry_backoff=10,
    retry_backoff_max=300,
    retry_jitter=True,
    max_retries=5,
)
def send_templated_email(self, *, to: str, subject: str, template: str, context: dict) -> None:
    """
    Render `<template>.txt` and `<template>.html` and send them as one email.

    The context must be JSON-serialisable (it travels through Redis).
    """
    text_body = render_to_string(f"{template}.txt", context)
    html_body = render_to_string(f"{template}.html", context)
    message = EmailMultiAlternatives(
        subject=subject,
        body=text_body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[to],
    )
    message.attach_alternative(html_body, "text/html")
    message.send(fail_silently=False)
    # Log the template only, never the code or other personal data.
    logger.info("Sent email template=%s task=%s", template, self.request.id)


# ---------------------------------------------------------------------------
# Telegram staff alerts
# ---------------------------------------------------------------------------
@shared_task(
    autoretry_for=(TelegramTemporaryError,),
    retry_backoff=15,
    retry_backoff_max=600,
    retry_jitter=True,
    max_retries=5,
)
def notify_payment(intent_id: int, event: str) -> None:
    """
    Tell the staff Telegram group about an approved payment or one that needs
    review, with the slip photo attached when there is one.
    """
    from apps.payments.models import PaymentIntent, PaymentSlip

    intent = PaymentIntent.objects.select_related("member", "tier").filter(pk=intent_id).first()
    if intent is None:
        return
    slip = intent.slips.exclude(status=PaymentSlip.Status.REJECTED).first()

    heading = {"approved": "Payment approved", "review": "Payment needs review"}.get(event, "Payment update")
    member = intent.member
    lines = [
        f"<b>{escape(heading)}</b>",
        "",
        f"Member: {escape(member.full_name)} (@{escape(member.handle)})",
        f"Seal: {escape(intent.tier.name)}",
        f"Amount: {intent.amount_satang / 100:,.2f} THB",
        f"Reference: <code>{escape(intent.reference)}</code>",
    ]
    if slip and slip.trans_ref:
        lines.append(f"Bank ref: <code>{escape(slip.trans_ref)}</code>")
    if event == "review" and slip and slip.note:
        lines.append(f"Reason: {escape(slip.note)}")
    caption = "\n".join(lines)

    if slip and slip.image:
        with slip.image.open("rb") as fh:
            telegram.send_photo(fh.read(), caption)
    else:
        telegram.send_message(caption)
