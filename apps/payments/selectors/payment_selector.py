from django.db.models import Prefetch
from django.shortcuts import get_object_or_404

from ..models import PaymentIntent, PaymentSlip


def member_intent_or_404(member, reference: str) -> PaymentIntent:
    """A member can only ever see their own payments."""
    return get_object_or_404(PaymentIntent.objects.select_related("tier"), member=member, reference=reference)


def open_intent(member) -> PaymentIntent | None:
    return (
        PaymentIntent.objects.select_related("tier")
        .filter(member=member, status__in=PaymentIntent.OPEN_STATUSES)
        .first()
    )


def review_queue():
    """Payments staff need to look at, oldest first."""
    return (
        PaymentIntent.objects.filter(status__in=[PaymentIntent.Status.REVIEW, PaymentIntent.Status.VERIFYING])
        .select_related("member", "tier")
        .order_by("updated_at")
    )


def recent_decided(limit=20):
    return (
        PaymentIntent.objects.filter(status__in=[PaymentIntent.Status.APPROVED, PaymentIntent.Status.REJECTED])
        .select_related("member", "tier", "decided_by")
        .order_by("-decided_at")[:limit]
    )


def staff_intent_or_404(reference: str) -> PaymentIntent:
    slips = PaymentSlip.objects.order_by("-created_at")
    return get_object_or_404(
        PaymentIntent.objects.select_related("member", "tier", "decided_by").prefetch_related(
            Prefetch("slips", queryset=slips)
        ),
        reference=reference,
    )


def slip_or_404(slip_id: int) -> PaymentSlip:
    return get_object_or_404(PaymentSlip.objects.select_related("intent"), pk=slip_id)
