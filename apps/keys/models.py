from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils.translation import gettext_lazy as _


class KeysAccount(models.Model):
    """
    A member's current key balance. Only ledger_service changes it, always
    together with a KeysEntry, and the database refuses a negative balance.
    """

    member = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="keys_account")
    balance = models.IntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.CheckConstraint(condition=Q(balance__gte=0), name="keys_balance_not_negative")]

    def __str__(self):
        return f"{self.member_id}: {self.balance}"


class KeysEntry(models.Model):
    """One immutable line in the keys ledger."""

    class Reason(models.TextChoices):
        SIGNUP_BONUS = "signup_bonus", _("Welcome keys")
        SEAL_PURCHASE = "seal_purchase", _("Seal purchase")
        REDEEM = "redeem", _("Treasure unlocked")
        REDEEM_REFUND = "redeem_refund", _("Treasure refund")
        CHECKIN = "checkin", _("Check-in")
        SPENDING = "spending", _("Club spending")
        ADMIN_ADJUST = "admin_adjust", _("Adjustment")
        PRIZE = "prize", _("Prize")

    account = models.ForeignKey(KeysAccount, on_delete=models.CASCADE, related_name="entries")
    delta = models.IntegerField()
    balance_after = models.IntegerField()
    reason = models.CharField(max_length=20, choices=Reason.choices)
    # What caused the entry, e.g. "intent:LSABC123" or "redemption:42".
    # Unique per reason when set, so retries can never post twice.
    reference = models.CharField(max_length=64, blank=True)
    note = models.CharField(max_length=255, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [models.Index(fields=["account", "-created_at"], name="keys_entry_history_idx")]
        constraints = [
            models.CheckConstraint(condition=~Q(delta=0), name="keys_entry_delta_not_zero"),
            models.CheckConstraint(condition=Q(balance_after__gte=0), name="keys_entry_balance_not_negative"),
            models.UniqueConstraint(
                fields=["reason", "reference"], condition=~Q(reference=""), name="keys_entry_idempotent"
            ),
        ]

    def __str__(self):
        return f"{self.delta:+d} {self.reason}"
