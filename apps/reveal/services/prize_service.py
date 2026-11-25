"""Editing the wheel's prizes. The wheel must always be spinnable."""

from django.db import transaction
from django.utils.translation import gettext as _

from apps.audit.services import audit_service

from ..models import WheelPrize

MIN_SEGMENTS = 2
MAX_SEGMENTS = 24
FIELDS = ("label", "description", "value_text", "weight", "sort_order", "is_active")


class PrizeError(Exception):
    """User-safe message."""


def _check_wheel():
    active = WheelPrize.objects.filter(is_active=True)
    count = active.count()
    if not MIN_SEGMENTS <= count <= MAX_SEGMENTS:
        raise PrizeError(
            _("The wheel needs between %(min)d and %(max)d active prizes.") % {"min": MIN_SEGMENTS, "max": MAX_SEGMENTS}
        )
    if not active.filter(weight__gt=0).exists():
        raise PrizeError(_("At least one active prize needs a weight above zero."))


def save(manager, prize: WheelPrize | None = None, **values) -> WheelPrize:
    """Create (prize=None) or update a prize. Rolled back if it would break the wheel."""
    with transaction.atomic():
        if prize is None:
            prize = WheelPrize.objects.create(**{f: values[f] for f in FIELDS if f in values})
            changes = {f: values[f] for f in FIELDS if f in values}
            action = "prize.create"
        else:
            prize = WheelPrize.objects.select_for_update().get(pk=prize.pk)
            changes = {}
            for field in FIELDS:
                if field in values and getattr(prize, field) != values[field]:
                    changes[field] = f"{getattr(prize, field)} -> {values[field]}"
                    setattr(prize, field, values[field])
            if not changes:
                return prize
            prize.save(update_fields=list(changes))
            action = "prize.update"
        _check_wheel()
        audit_service.record(manager, action, prize, **changes)
    return prize
