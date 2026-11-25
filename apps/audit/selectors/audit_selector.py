from ..models import AuditEntry


def recent(action_prefix: str = "", limit: int = 200):
    qs = AuditEntry.objects.select_related("actor")
    if action_prefix:
        qs = qs.filter(action__startswith=action_prefix)
    return qs[:limit]


def for_target(target, limit: int = 50):
    return AuditEntry.objects.filter(target_type=target._meta.label_lower, target_id=str(target.pk)).select_related(
        "actor"
    )[:limit]


def action_prefixes():
    return ["member", "keys", "membership", "payment", "treasure", "prize", "tier", "reveal", "broadcast"]
