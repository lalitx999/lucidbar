from django.conf import settings
from django.db import models


class AuditEntry(models.Model):
    """
    One manager or staff action that changed something important. Rows are
    only ever inserted; the dashboard has no edit or delete for them.
    """

    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    action = models.CharField(max_length=40, db_index=True)  # e.g. "member.suspend"
    target_type = models.CharField(max_length=40, blank=True)
    target_id = models.CharField(max_length=40, blank=True)
    target_label = models.CharField(max_length=150, blank=True)
    details = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [models.Index(fields=["target_type", "target_id"], name="audit_target_idx")]

    def __str__(self):
        return f"{self.created_at:%Y-%m-%d %H:%M} {self.action}"
