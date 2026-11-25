from celery import shared_task

from .services import whisper_service


@shared_task(acks_late=True, max_retries=3, autoretry_for=(Exception,), retry_backoff=30)
def fan_out_broadcast(broadcast_id: int) -> int:
    """Deliver a broadcast to every recipient. Safe to retry (skips delivered)."""
    return whisper_service.fan_out(broadcast_id)
