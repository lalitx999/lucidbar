"""Small numbers for the manager overview. A handful of aggregate queries."""

import datetime as dt

from django.db.models import Count, Q, Sum
from django.utils import timezone

from apps.accounts.models import Member
from apps.checkin.models import CheckIn
from apps.core.clock import business_night
from apps.keys.models import KeysEntry, Spending
from apps.memberships.models import Membership
from apps.payments.models import PaymentIntent
from apps.treasures.models import Redemption


def month_start(now=None):
    local = timezone.localtime(now or timezone.now())
    return local.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def overview() -> dict:
    now = timezone.now()
    since = month_start(now)
    members = Member.objects.filter(is_staff=False).aggregate(
        total=Count("pk"),
        active=Count("pk", filter=Q(status=Member.Status.ACTIVE)),
        suspended=Count("pk", filter=Q(status=Member.Status.SUSPENDED)),
        new_this_month=Count("pk", filter=Q(date_joined__gte=since)),
    )
    paid_holders = (
        Membership.objects.filter(tier__price_satang__gt=0, starts_at__lte=now, ends_at__gt=now)
        .values("tier__name")
        .annotate(n=Count("member", distinct=True))
        .order_by("tier__name")
    )
    revenue = PaymentIntent.objects.filter(status=PaymentIntent.Status.APPROVED, decided_at__gte=since).aggregate(
        satang=Sum("amount_satang"), count=Count("pk")
    )
    keys = KeysEntry.objects.filter(created_at__gte=since).aggregate(
        issued=Sum("delta", filter=Q(delta__gt=0)), spent=Sum("delta", filter=Q(delta__lt=0))
    )
    spending = Spending.objects.filter(created_at__gte=since).aggregate(satang=Sum("amount_satang"))
    week_from = business_night(now) - dt.timedelta(days=6)
    return {
        "since": since,
        "members": members,
        "paid_holders": list(paid_holders),
        "revenue_thb": (revenue["satang"] or 0) / 100,
        "payments_count": revenue["count"],
        "keys_issued": keys["issued"] or 0,
        "keys_spent": -(keys["spent"] or 0),
        "spending_thb": (spending["satang"] or 0) / 100,
        "checkins_7d": CheckIn.objects.filter(night__gte=week_from).count(),
        "redemptions_month": Redemption.objects.filter(created_at__gte=since)
        .exclude(status=Redemption.Status.CANCELLED)
        .count(),
        "review_queue": PaymentIntent.objects.filter(status=PaymentIntent.Status.REVIEW).count(),
    }
