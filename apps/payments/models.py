import uuid

from django.conf import settings
from django.core.files.storage import storages
from django.db import models
from django.db.models import Q
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


def private_storage():
    # Resolved lazily so tests can swap the backend through STORAGES.
    return storages["private"]


def slip_upload_path(instance, filename):
    # Random name: never trust or expose the uploaded file name.
    now = timezone.now()
    return f"slips/{now:%Y/%m}/{uuid.uuid4().hex}.jpg"


class PaymentIntent(models.Model):
    """One attempt to buy a paid Seal tier, from checkout to decision."""

    class Status(models.TextChoices):
        AWAITING_SLIP = "awaiting_slip", _("Awaiting slip")
        VERIFYING = "verifying", _("Verifying")
        REVIEW = "review", _("Staff review")
        APPROVED = "approved", _("Approved")
        REJECTED = "rejected", _("Rejected")
        EXPIRED = "expired", _("Expired")
        CANCELLED = "cancelled", _("Cancelled")

    OPEN_STATUSES = (Status.AWAITING_SLIP, Status.VERIFYING, Status.REVIEW)

    member = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="payment_intents")
    tier = models.ForeignKey("memberships.SealTier", on_delete=models.PROTECT, related_name="payment_intents")
    reference = models.CharField(max_length=16, unique=True)
    amount_satang = models.PositiveIntegerField()
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.AWAITING_SLIP, db_index=True)
    # Shown to the member: why the last slip was not accepted, or the staff decision.
    status_message = models.CharField(max_length=255, blank=True)
    expires_at = models.DateTimeField()
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    decided_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            # A member can only have one checkout in progress at a time.
            models.UniqueConstraint(
                fields=["member"],
                condition=Q(status__in=["awaiting_slip", "verifying", "review"]),
                name="one_open_payment_intent",
            ),
            models.CheckConstraint(condition=Q(amount_satang__gt=0), name="intent_amount_positive"),
        ]

    def __str__(self):
        return self.reference

    @property
    def amount_thb(self):
        return self.amount_satang / 100

    @property
    def is_open(self):
        return self.status in self.OPEN_STATUSES


class PaymentSlip(models.Model):
    """An uploaded transfer slip and what EasySlip (or staff) said about it."""

    class Status(models.TextChoices):
        PENDING = "pending", _("Pending")
        VERIFIED = "verified", _("Verified")
        REJECTED = "rejected", _("Rejected")
        REVIEW = "review", _("Staff review")

    intent = models.ForeignKey(PaymentIntent, on_delete=models.PROTECT, related_name="slips")
    image = models.ImageField(upload_to=slip_upload_path, storage=private_storage)
    sha256 = models.CharField(max_length=64, db_index=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    # Bank transaction reference. Unique: one real transfer can pay only once.
    trans_ref = models.CharField(max_length=64, unique=True, null=True, blank=True)
    slip_amount_satang = models.PositiveIntegerField(null=True, blank=True)
    slip_date = models.DateTimeField(null=True, blank=True)
    provider_code = models.CharField(max_length=40, blank=True)
    provider_response = models.JSONField(null=True, blank=True)
    note = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    checked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"slip {self.pk} for {self.intent_id}"
