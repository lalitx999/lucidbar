"""Editing seal tiers (prices, periods, keys, benefits) from the dashboard."""

from django.db import transaction
from django.utils.translation import gettext as _

from apps.audit.services import audit_service

from ..models import SealTier

EDITABLE = ("name", "tagline", "price_satang", "period_days", "initial_keys", "benefits", "is_active")


class TierError(Exception):
    """User-safe message."""


def update(tier: SealTier, manager, **values) -> SealTier:
    with transaction.atomic():
        tier = SealTier.objects.select_for_update().get(pk=tier.pk)
        new_price = values.get("price_satang", tier.price_satang)
        if (tier.price_satang == 0) != (new_price == 0):
            raise TierError(_("A free tier cannot become paid, or the other way round."))
        if new_price and not values.get("period_days", tier.period_days):
            raise TierError(_("A paid tier needs a period in days."))
        if tier.price_satang == 0 and values.get("is_active") is False:
            others = SealTier.objects.filter(is_active=True, price_satang=0).exclude(pk=tier.pk)
            if not others.exists():
                raise TierError(_("New members need a free tier. Keep this one active."))
        changes = {}
        for field in EDITABLE:
            if field in values and getattr(tier, field) != values[field]:
                changes[field] = f"{getattr(tier, field)} -> {values[field]}"
                setattr(tier, field, values[field])
        if changes:
            tier.save(update_fields=list(changes))
            audit_service.record(manager, "tier.update", tier, **changes)
    return tier
