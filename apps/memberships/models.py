from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils.translation import gettext_lazy as _


class SealTier(models.Model):
    """
    A membership level (Bronze, Gold, Obsidian). Prices live here, never in
    code, so managers can change them from the dashboard.
    """

    code = models.SlugField(max_length=20, unique=True)
    name = models.CharField(max_length=50)
    tagline = models.CharField(max_length=120, blank=True)
    price_satang = models.PositiveIntegerField(default=0, help_text=_("Price in satang (100 satang = 1 THB)."))
    period_days = models.PositiveSmallIntegerField(default=30, help_text=_("0 means it never expires."))
    initial_keys = models.PositiveSmallIntegerField(default=0)
    benefits = models.TextField(blank=True, help_text=_("One benefit per line."))
    sort_order = models.PositiveSmallIntegerField(default=0, help_text=_("Higher is a better tier."))
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["sort_order"]
        constraints = [
            models.CheckConstraint(
                condition=Q(price_satang=0) | Q(period_days__gt=0),
                name="paid_tier_has_period",
            )
        ]

    def __str__(self):
        return self.name

    @property
    def is_free(self):
        return self.price_satang == 0

    @property
    def price_thb(self):
        return self.price_satang / 100

    @property
    def benefit_list(self):
        return [line.strip() for line in self.benefits.splitlines() if line.strip()]


class Membership(models.Model):
    """A period during which a member holds a tier. History is kept."""

    class Source(models.TextChoices):
        SIGNUP = "signup", _("Signup")
        PAYMENT = "payment", _("Payment")
        STAFF = "staff", _("Granted by staff")

    member = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="memberships")
    tier = models.ForeignKey(SealTier, on_delete=models.PROTECT, related_name="memberships")
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField(null=True, blank=True, help_text=_("Empty means no expiry."))
    source = models.CharField(max_length=10, choices=Source.choices)
    payment_intent = models.OneToOneField(
        "payments.PaymentIntent",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="membership",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["member", "ends_at"], name="membership_active_idx")]
        constraints = [
            models.CheckConstraint(
                condition=Q(ends_at__isnull=True) | Q(ends_at__gt=models.F("starts_at")),
                name="membership_ends_after_start",
            ),
            # One signup (Bronze) grant per member.
            models.UniqueConstraint(fields=["member"], condition=Q(source="signup"), name="one_signup_membership"),
        ]

    def __str__(self):
        return f"{self.member_id} {self.tier.code} {self.starts_at:%Y-%m-%d}"
