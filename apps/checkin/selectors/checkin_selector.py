from django.db.models import Count, Max

from apps.core.clock import business_night

from ..models import CheckIn


def tonight(limit: int = 200):
    return (
        CheckIn.objects.filter(night=business_night())
        .select_related("member", "created_by")
        .order_by("-created_at")[:limit]
    )


def checkin_or_none(checkin_id):
    if not str(checkin_id or "").isdigit():
        return None
    return CheckIn.objects.select_related("member", "created_by").filter(pk=checkin_id).first()


def visit_summary(member) -> dict:
    """Total visits and the last visit date, for the Identity page (one query)."""
    return CheckIn.objects.filter(member=member).aggregate(visits=Count("id"), last_night=Max("night"))
