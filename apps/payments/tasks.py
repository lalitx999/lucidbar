import logging

from celery import shared_task

from .clients import easyslip
from .models import PaymentIntent, PaymentSlip
from .services import payment_service, slip_decision

logger = logging.getLogger(__name__)

MAX_RETRIES = 6


@shared_task(bind=True, max_retries=MAX_RETRIES, acks_late=True)
def verify_slip_task(self, slip_id: int) -> None:
    """
    Check one slip with EasySlip and apply the decision.

    Temporary failures retry with growing delays (about 30 s up to 15 min).
    If they never clear, the payment goes to staff review instead of
    leaving the member stuck.
    """
    slip = PaymentSlip.objects.select_related("intent").filter(pk=slip_id).first()
    if slip is None or slip.status != PaymentSlip.Status.PENDING:
        return
    intent = slip.intent
    if intent.status != PaymentIntent.Status.VERIFYING:
        return

    try:
        with slip.image.open("rb") as fh:
            image = fh.read()
        result = easyslip.verify_slip(image, intent.amount_satang)
    except easyslip.EasySlipTemporaryError as exc:
        if self.request.retries >= MAX_RETRIES:
            logger.warning("EasySlip still failing for slip %s after retries: %s", slip_id, exc)
            payment_service.send_to_review(slip_id, f"Automatic check unavailable ({exc})")
            return
        countdown = exc.retry_after or min(30 * (2**self.request.retries), 900)
        raise self.retry(exc=exc, countdown=countdown) from exc

    trans_ref = str(((result.data or {}).get("rawSlip") or {}).get("transRef") or "").strip()
    trans_ref_used = bool(trans_ref) and PaymentSlip.objects.filter(trans_ref=trans_ref).exclude(pk=slip_id).exists()

    decision = slip_decision.decide(
        result=result,
        expected_satang=intent.amount_satang,
        checkout_started=intent.created_at,
        trans_ref_used=trans_ref_used,
    )
    payment_service.apply_decision(
        slip_id,
        decision,
        provider_code=result.code or ("OK" if result.ok else ""),
        provider_response={"ok": result.ok, "code": result.code, "message": result.message, "data": result.data},
    )
