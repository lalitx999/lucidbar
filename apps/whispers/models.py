from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


class Broadcast(models.Model):
    """A message staff sent to many members at once."""

    class Audience(models.TextChoices):
        ALL = "all", _("All active members")
        PAID = "paid", _("Gold and Obsidian holders")

    title = models.CharField(max_length=120)
    body = models.TextField(max_length=2000)
    audience = models.CharField(max_length=10, choices=Audience.choices, default=Audience.ALL)
    sent_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+")
    recipients = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title


class Whisper(models.Model):
    """One message in a member's private inbox."""

    class Kind(models.TextChoices):
        SYSTEM = "system", _("Notice")
        PAYMENT = "payment", _("Payment")
        TREASURE = "treasure", _("Treasure")
        REVEAL = "reveal", _("Reveal")
        BROADCAST = "broadcast", _("Announcement")
        BOOKING = "booking", _("Booking")
        VISIT = "visit", _("Visit")

    member = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="whispers")
    kind = models.CharField(max_length=10, choices=Kind.choices, default=Kind.SYSTEM)
    title = models.CharField(max_length=120)
    body = models.TextField(max_length=2000, blank=True)
    broadcast = models.ForeignKey(Broadcast, on_delete=models.CASCADE, null=True, blank=True, related_name="whispers")
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["member", "-created_at"], name="whisper_inbox_idx"),
            models.Index(fields=["member"], condition=models.Q(is_read=False), name="whisper_unread_idx"),
        ]

    def __str__(self):
        return self.title
