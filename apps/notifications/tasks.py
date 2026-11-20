"""
Outbound notifications. Every send runs in a Celery worker, never in a request.

Email goes through Django's configured backend (Hostinger SMTP in production,
console in local development).
"""

import logging
import smtplib
import socket

from celery import shared_task
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string

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
