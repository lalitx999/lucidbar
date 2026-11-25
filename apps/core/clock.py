"""
Club time. A night at the club runs past midnight, so a visit at 01:00 on
Saturday belongs to Friday night. The "business night" changes over at
BUSINESS_DAY_STARTS_HOUR (local time, Asia/Bangkok).
"""

import datetime as dt

from django.conf import settings
from django.utils import timezone


def business_night(moment: dt.datetime | None = None) -> dt.date:
    local = timezone.localtime(moment or timezone.now())
    return (local - dt.timedelta(hours=settings.BUSINESS_DAY_STARTS_HOUR)).date()


def night_start(night: dt.date, slot: dt.time) -> dt.datetime:
    """Aware datetime for a time slot on a given night (early-morning slots fall on the next day)."""
    day = night + dt.timedelta(days=1) if slot.hour < settings.BUSINESS_DAY_STARTS_HOUR else night
    return timezone.make_aware(dt.datetime.combine(day, slot))
