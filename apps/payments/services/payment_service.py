"""
Checkout, slip submission, and the final approve / reject decisions.

All state changes lock the PaymentIntent row (select_for_update) so a slow
worker, a double click and a staff action can never approve twice.
"""

import logging
import secrets
from datetime import timedelta

from django.conf import settings
from django.core.files.base import ContentFile
from django.db import IntegrityError, transaction
from django.utils import timezone
from django.utils.translation import gettext as _

from apps.audit.services import audit_service
from apps.memberships.models import SealTier
from apps.memberships.services import membership_service
from apps.whispers.models import Whisper
from apps.whispers.services import whisper_service

from ..models import PaymentIntent, PaymentSlip
from ..slip_image import SlipImageError, clean_slip
from . import slip_decision

logger = logging.getLogger(__name__)
REFERENCE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


class PaymentError(Exception):
    """User-safe message."""


def _new_reference():
    return "LS" + "".join(secrets.choice(REFERENCE_ALPHABET) for _ in range(8))


def _lock(intent_id) -> PaymentIntent:
    return PaymentIntent.objects.select_for_update().select_related("tier", "member").get(pk=intent_id)


def expire_if_due(intent: PaymentIntent) -> PaymentIntent:
    """Lazily expire an unpaid checkout once its time is up."""
    if intent.status == PaymentIntent.Status.AWAITING_SLIP and intent.expires_at <= timezone.now():
        PaymentIntent.objects.filter(pk=intent.pk, status=PaymentIntent.Status.AWAITING_SLIP).update(
            status=PaymentIntent.Status.EXPIRED, updated_at=timezone.now()
        )
        intent.refresh_from_db()
    return intent


# ---------------------------------------------------------------------------
# Checkout
# ---------------------------------------------------------------------------
def start_checkout(member, tier: SealTier) -> PaymentIntent:
    """
    Open a checkout for a paid tier, or return the one already open.

    While a slip is being verified or reviewed the member cannot start another
    checkout. An unpaid checkout for a different tier is cancelled.
    """
    if tier.is_free or not tier.is_active:
        raise PaymentError(_("This seal cannot be purchased."))

    with transaction.atomic():
        open_intent = (
            PaymentIntent.objects.select_for_update()
            .filter(member=member, status__in=PaymentIntent.OPEN_STATUSES)
            .first()
        )
        if open_intent:
            open_intent = expire_if_due(open_intent)
        if open_intent and open_intent.is_open:
            if open_intent.status != PaymentIntent.Status.AWAITING_SLIP or open_intent.tier_id == tier.id:
                return open_intent
            open_intent.status = PaymentIntent.Status.CANCELLED
            open_intent.save(update_fields=["status", "updated_at"])

        for _attempt in range(5):
            try:
                with transaction.atomic():
                    return PaymentIntent.objects.create(
                        member=member,
                        tier=tier,
                        reference=_new_reference(),
                        amount_satang=tier.price_satang,
                        expires_at=timezone.now() + timedelta(hours=settings.PAYMENT_INTENT_TTL_HOURS),
                    )
            except IntegrityError:
                if PaymentIntent.objects.filter(member=member, status__in=PaymentIntent.OPEN_STATUSES).exists():
                    raise PaymentError(_("You already have a payment in progress.")) from None
        raise RuntimeError("Could not allocate a unique payment reference")


def cancel_checkout(intent: PaymentIntent) -> None:
    with transaction.atomic():
        intent = _lock(intent.pk)
        if intent.status != PaymentIntent.Status.AWAITING_SLIP:
            raise PaymentError(_("This payment can no longer be cancelled."))
        intent.status = PaymentIntent.Status.CANCELLED
        intent.save(update_fields=["status", "updated_at"])


# ---------------------------------------------------------------------------
# Slip upload
# ---------------------------------------------------------------------------
def submit_slip(intent: PaymentIntent, uploaded) -> PaymentSlip:
    """Store a cleaned slip image and queue automatic verification."""
    from ..tasks import verify_slip_task  # local import: tasks import this module

    try:
        cleaned = clean_slip(uploaded)
    except SlipImageError as exc:
        raise PaymentError(str(exc)) from None

    # Expire first, in its own commit, so the refusal below does not roll it back.
    intent = expire_if_due(intent)
    with transaction.atomic():
        intent = _lock(intent.pk)
        if intent.status != PaymentIntent.Status.AWAITING_SLIP:
            raise PaymentError(_("This payment is not waiting for a slip."))
        if intent.slips.count() >= settings.SLIP_MAX_UPLOADS_PER_INTENT:
            raise PaymentError(_("Too many uploads for this payment. Please contact the club."))
        if PaymentSlip.objects.filter(sha256=cleaned.sha256).exclude(status=PaymentSlip.Status.REJECTED).exists():
            raise PaymentError(_("This slip has already been uploaded."))

        slip = PaymentSlip(intent=intent, sha256=cleaned.sha256)
        slip.image.save("slip.jpg", ContentFile(cleaned.content), save=False)
        slip.save()

        intent.status = PaymentIntent.Status.VERIFYING
        intent.status_message = ""
        intent.save(update_fields=["status", "status_message", "updated_at"])
        transaction.on_commit(lambda: verify_slip_task.delay(slip.pk))
    return slip


# ---------------------------------------------------------------------------
# Applying a verification result
# ---------------------------------------------------------------------------
def apply_decision(slip_id: int, decision: slip_decision.Decision, provider_code="", provider_response=None) -> None:
    """Record what EasySlip said and move the intent to its next state."""
    from apps.notifications.tasks import notify_payment

    with transaction.atomic():
        slip = PaymentSlip.objects.select_for_update().get(pk=slip_id)
        intent = _lock(slip.intent_id)
        if intent.status != PaymentIntent.Status.VERIFYING or slip.status != PaymentSlip.Status.PENDING:
            logger.info("Slip %s already handled; skipping", slip_id)
            return

        slip.provider_code = provider_code
        slip.provider_response = provider_response
        slip.slip_amount_satang = decision.amount_satang
        slip.slip_date = decision.slip_date
        slip.note = decision.reason[:255]
        slip.checked_at = timezone.now()

        if decision.action == slip_decision.APPROVE:
            slip.trans_ref = decision.trans_ref
            slip.status = PaymentSlip.Status.VERIFIED
            try:
                with transaction.atomic():
                    slip.save()
            except IntegrityError:
                # Lost a race: the same transfer was just used elsewhere.
                decision = slip_decision.Decision(slip_decision.RETRY_UPLOAD, _("This slip has already been used."))
                slip.trans_ref = None
            else:
                _approve(intent, by=None)
                transaction.on_commit(lambda: notify_payment.delay(intent.pk, "approved"))
                return

        if decision.action == slip_decision.RETRY_UPLOAD:
            slip.status = PaymentSlip.Status.REJECTED
            slip.save()
            intent.status = PaymentIntent.Status.AWAITING_SLIP
            intent.status_message = decision.reason[:255]
            intent.save(update_fields=["status", "status_message", "updated_at"])
            return

        # REVIEW
        slip.status = PaymentSlip.Status.REVIEW
        slip.trans_ref = None
        slip.save()
        intent.status = PaymentIntent.Status.REVIEW
        intent.status_message = _("Your slip is being checked by our team.")
        intent.save(update_fields=["status", "status_message", "updated_at"])
        transaction.on_commit(lambda: notify_payment.delay(intent.pk, "review"))


def send_to_review(slip_id: int, reason: str) -> None:
    apply_decision(slip_id, slip_decision.Decision(slip_decision.REVIEW, reason), provider_code="RETRIES_EXHAUSTED")


def _approve(intent: PaymentIntent, by) -> None:
    """Caller holds the intent lock inside a transaction."""
    intent.status = PaymentIntent.Status.APPROVED
    intent.status_message = ""
    intent.decided_by = by
    intent.decided_at = timezone.now()
    intent.save(update_fields=["status", "status_message", "decided_by", "decided_at", "updated_at"])
    membership = membership_service.grant_paid_membership(intent.member, intent.tier, intent)
    whisper_service.send(
        intent.member,
        _("%(tier)s activated") % {"tier": intent.tier.name},
        _("Payment %(ref)s confirmed. Active until %(date)s. %(keys)d keys added.")
        % {
            "ref": intent.reference,
            "date": timezone.localtime(membership.ends_at).strftime("%d %b %Y"),
            "keys": intent.tier.initial_keys,
        },
        kind=Whisper.Kind.PAYMENT,
    )


# ---------------------------------------------------------------------------
# Staff decisions
# ---------------------------------------------------------------------------
def staff_approve(intent: PaymentIntent, staff, trans_ref: str = "") -> None:
    from apps.notifications.tasks import notify_payment

    with transaction.atomic():
        intent = _lock(intent.pk)
        if intent.status not in (PaymentIntent.Status.REVIEW, PaymentIntent.Status.VERIFYING):
            raise PaymentError(_("Only payments under review can be approved."))
        slip = intent.slips.select_for_update().exclude(status=PaymentSlip.Status.REJECTED).first()
        if slip:
            slip.status = PaymentSlip.Status.VERIFIED
            slip.note = f"Approved by staff {staff.pk}"
            if trans_ref:
                slip.trans_ref = trans_ref.strip()
            try:
                with transaction.atomic():
                    slip.save()
            except IntegrityError:
                raise PaymentError(_("That bank reference is already used by another payment.")) from None
        _approve(intent, by=staff)
        audit_service.record(
            staff, "payment.approve", intent.member, reference=intent.reference, trans_ref=trans_ref.strip()
        )
        transaction.on_commit(lambda: notify_payment.delay(intent.pk, "approved"))


def staff_reject(intent: PaymentIntent, staff, reason: str, allow_new_slip: bool = True) -> None:
    with transaction.atomic():
        intent = _lock(intent.pk)
        if intent.status not in (PaymentIntent.Status.REVIEW, PaymentIntent.Status.VERIFYING):
            raise PaymentError(_("Only payments under review can be rejected."))
        intent.slips.exclude(status=PaymentSlip.Status.REJECTED).update(
            status=PaymentSlip.Status.REJECTED, note=f"Rejected by staff {staff.pk}"
        )
        intent.status = PaymentIntent.Status.AWAITING_SLIP if allow_new_slip else PaymentIntent.Status.REJECTED
        intent.status_message = reason[:255]
        intent.decided_by = staff
        intent.decided_at = timezone.now()
        if allow_new_slip:
            # Give the member a fresh window to upload a correct slip.
            intent.expires_at = timezone.now() + timedelta(hours=settings.PAYMENT_INTENT_TTL_HOURS)
        intent.save(update_fields=["status", "status_message", "decided_by", "decided_at", "expires_at", "updated_at"])
        audit_service.record(
            staff,
            "payment.reject",
            intent.member,
            reference=intent.reference,
            reason=reason,
            allow_new_slip=allow_new_slip,
        )
        whisper_service.send(
            intent.member,
            _("Payment %(ref)s not accepted") % {"ref": intent.reference},
            intent.status_message,
            kind=Whisper.Kind.PAYMENT,
        )
