import uuid

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


def treasure_image_path(instance, filename):
    return f"treasures/{timezone.now():%Y/%m}/{uuid.uuid4().hex}.jpg"


class Treasure(models.Model):
    """A reward in the catalogue that members unlock with keys."""

    class Category(models.TextChoices):
        SPIRITS = "spirits", _("Spirits and champagne")
        CIGARS = "cigars", _("Cigars")
        EXPERIENCES = "experiences", _("VIP experiences")
        MERCHANDISE = "merchandise", _("Merchandise")
        OTHER = "other", _("Other")

    name = models.CharField(max_length=120)
    category = models.CharField(max_length=20, choices=Category.choices, default=Category.OTHER)
    description = models.TextField(blank=True)
    image = models.ImageField(upload_to=treasure_image_path, blank=True)
    keys_cost = models.PositiveIntegerField()
    stock = models.PositiveIntegerField(null=True, blank=True, help_text=_("Empty means unlimited."))
    is_featured = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["sort_order", "keys_cost", "name"]
        constraints = [models.CheckConstraint(condition=Q(keys_cost__gt=0), name="treasure_cost_positive")]

    def __str__(self):
        return self.name

    @property
    def in_stock(self):
        return self.stock is None or self.stock > 0


class Redemption(models.Model):
    """A treasure a member unlocked. Staff hand it over at the club."""

    class Status(models.TextChoices):
        READY = "ready", _("Ready to collect")
        HANDED_OVER = "handed_over", _("Collected")
        CANCELLED = "cancelled", _("Cancelled")

    member = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="redemptions")
    treasure = models.ForeignKey(Treasure, on_delete=models.PROTECT, related_name="redemptions")
    keys_spent = models.PositiveIntegerField()
    # Short code the member shows at the bar; staff look it up.
    claim_code = models.CharField(max_length=8, unique=True)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.READY, db_index=True)
    handled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    handled_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.claim_code} {self.treasure_id}"
