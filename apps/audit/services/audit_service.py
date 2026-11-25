"""Write audit entries. Call inside the same transaction as the change it records."""

from ..models import AuditEntry


def record(actor, action: str, target=None, **details) -> AuditEntry:
    target_type = target_id = target_label = ""
    if target is not None:
        target_type = target._meta.label_lower
        target_id = str(target.pk)
        target_label = str(getattr(target, "full_name", None) or target)[:150]
    clean = {k: v if isinstance(v, (int, float, bool, type(None))) else str(v) for k, v in details.items()}
    return AuditEntry.objects.create(
        actor=actor,
        action=action,
        target_type=target_type,
        target_id=target_id,
        target_label=target_label,
        details=clean,
    )
