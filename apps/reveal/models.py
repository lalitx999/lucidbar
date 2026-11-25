from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils.translation import gettext_lazy as _


class Epoch(models.Model):
    """One Reveal week (ISO week, Bangkok time). Number is YYYYWW, e.g. 202648."""

    number = models.PositiveIntegerField(unique=True)
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()

    class Meta:
        ordering = ["-number"]

    def __str__(self):
        return f"Epoch {self.number}"

    @property
    def label(self):
        return f"{self.number // 100} W{self.number % 100:02d}"


class ChosenDraw(models.Model):
    """The weekly draw. One per epoch; the winner may spin the wheel once."""

    epoch = models.OneToOneField(Epoch, on_delete=models.PROTECT, related_name="draw")
    winner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="chosen_draws")
    eligible_count = models.PositiveIntegerField()
    drawn_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.epoch} -> {self.winner_id}"


class WheelPrize(models.Model):
    """One of the wheel's segments. Weight sets how likely it is (relative)."""

    label = models.CharField(max_length=40)
    description = models.CharField(max_length=120, blank=True)
    value_text = models.CharField(max_length=60, blank=True)
    weight = models.PositiveIntegerField(default=1, help_text=_("Relative chance. 0 removes it from the draw."))
    sort_order = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["sort_order", "pk"]

    def __str__(self):
        return self.label


class WheelSpin(models.Model):
    """The Chosen's spin and the prize it won, collected at the club."""

    class Status(models.TextChoices):
        READY = "ready", _("Ready to collect")
        HANDED_OVER = "handed_over", _("Collected")

    draw = models.OneToOneField(ChosenDraw, on_delete=models.PROTECT, related_name="spin")
    member = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="wheel_spins")
    prize = models.ForeignKey(WheelPrize, on_delete=models.PROTECT, related_name="spins")
    segment_index = models.PositiveSmallIntegerField()
    claim_code = models.CharField(max_length=8, unique=True)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.READY)
    handled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    handled_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [models.CheckConstraint(condition=Q(segment_index__lt=24), name="spin_segment_in_range")]

    def __str__(self):
        return f"{self.claim_code} {self.prize_id}"
