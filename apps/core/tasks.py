from celery import shared_task


@shared_task
def ping():
    """Trivial task used to confirm the Celery worker is wired up."""
    return "pong"
