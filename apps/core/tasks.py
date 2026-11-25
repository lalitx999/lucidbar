"""Celery tasks owned by core: a ping and the nightly housekeeping jobs (see CELERY_BEAT_SCHEDULE)."""

import logging

from celery import shared_task
from django.core.management import call_command

logger = logging.getLogger(__name__)


@shared_task
def ping():
    """Trivial task used to confirm the Celery worker is wired up."""
    return "pong"


@shared_task
def expire_unpaid_checkouts() -> int:
    from apps.payments.services import payment_service

    count = payment_service.expire_due_intents()
    if count:
        logger.info("Expired %d unpaid checkouts", count)
    return count


@shared_task
def purge_old_slip_images() -> int:
    from apps.payments.services import payment_service

    count = payment_service.purge_old_slip_images()
    if count:
        logger.info("Deleted %d old slip images", count)
    return count


@shared_task
def purge_old_otps() -> int:
    from apps.accounts.services import otp_service

    return otp_service.purge_old_codes()


@shared_task
def clear_expired_sessions() -> None:
    call_command("clearsessions")
