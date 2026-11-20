"""Granting memberships. Each grant credits the tier's keys in the same transaction."""

from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from apps.keys.models import KeysEntry
from apps.keys.services import ledger_service

from ..models import Membership, SealTier
from ..selectors import membership_selector


def grant_signup_membership(member) -> Membership | None:
    """
    Give a newly verified member the free tier. Safe to call twice: the
    one_signup_membership constraint and the existence check keep it single.
    """
    tier = membership_selector.signup_tier()
    if tier is None:
        return None
    existing = Membership.objects.filter(member=member, source=Membership.Source.SIGNUP).first()
    if existing:
        return existing
    with transaction.atomic():
        now = timezone.now()
        ends_at = now + timedelta(days=tier.period_days) if tier.period_days else None
        membership = Membership.objects.create(
            member=member, tier=tier, starts_at=now, ends_at=ends_at, source=Membership.Source.SIGNUP
        )
        _credit_keys(membership, KeysEntry.Reason.SIGNUP_BONUS)
    return membership


def grant_paid_membership(member, tier: SealTier, payment_intent) -> Membership:
    """
    Add one paid period. Renewing the same tier extends from the current end
    date, so paying early never loses days. A different tier starts now.
    """
    with transaction.atomic():
        now = timezone.now()
        start = membership_selector.latest_paid_end(member, tier, now) or now
        membership = Membership.objects.create(
            member=member,
            tier=tier,
            starts_at=start,
            ends_at=start + timedelta(days=tier.period_days),
            source=Membership.Source.PAYMENT,
            payment_intent=payment_intent,
        )
        _credit_keys(membership, KeysEntry.Reason.SEAL_PURCHASE)
    return membership


def _credit_keys(membership: Membership, reason: str) -> None:
    """Credit the tier's keys once per membership (idempotent by reference)."""
    if membership.tier.initial_keys:
        ledger_service.post_entry(
            membership.member,
            membership.tier.initial_keys,
            reason,
            reference=f"membership:{membership.pk}",
            note=membership.tier.name,
        )
