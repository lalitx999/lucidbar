from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


class CheckIn(models.Model):
    """A visit recorded at the door. One per member per club night."""

    class Method(models.TextChoices):
        STAFF_SCAN = "staff_scan", _("Card scanned by staff")

    member = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="checkins")
    night = models.DateField()
    method = models.CharField(max_length=12, choices=Method.choices, default=Method.STAFF_SCAN)
    keys_awarded = models.PositiveIntegerField(default=0)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [models.Index(fields=["night"], name="checkin_night_idx")]
        constraints = [models.UniqueConstraint(fields=["member", "night"], name="checkin_once_per_night")]

    def __str__(self):
        return f"{self.member_id} {self.night}"
