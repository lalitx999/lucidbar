from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.db.models.functions import Lower
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from .constants import COUNTRY_DIAL_CODES, NATIONALITIES


class MemberManager(BaseUserManager):
    use_in_migrations = True

    def _create(self, email, password, **extra):
        if not email:
            raise ValueError("Email is required")
        member = self.model(email=self.normalize_email(email).lower(), **extra)
        member.set_password(password)
        member.save(using=self._db)
        return member

    def create_user(self, email, password=None, **extra):
        extra.setdefault("is_staff", False)
        extra.setdefault("is_superuser", False)
        return self._create(email, password, **extra)

    def create_superuser(self, email, password=None, **extra):
        # Superusers are maintenance accounts; they skip the member onboarding.
        extra.update(is_staff=True, is_superuser=True, status=Member.Status.ACTIVE)
        extra.setdefault("email_verified_at", timezone.now())
        return self._create(email, password, **extra)

    def get_by_natural_key(self, username):
        # Case-insensitive login by email.
        return self.get(email__iexact=username)


class Member(AbstractBaseUser, PermissionsMixin):
    """
    A club member (and, with is_staff, a staff account).

    Login is by email. Emails are stored lower-case and unique regardless of case.
    """

    class Status(models.TextChoices):
        PENDING = "pending", _("Pending verification")
        ACTIVE = "active", _("Active")
        SUSPENDED = "suspended", _("Suspended")

    # unique=True for Django auth; the Lower() constraint below also blocks case variants.
    email = models.EmailField(_("email"), max_length=254, unique=True)
    full_name = models.CharField(_("full name"), max_length=150)
    handle = models.CharField(_("handle"), max_length=32, unique=True)
    country_code = models.CharField(_("country code"), max_length=5, choices=COUNTRY_DIAL_CODES, default="+66")
    phone = models.CharField(_("phone"), max_length=15)
    date_of_birth = models.DateField(_("date of birth"), null=True)
    nationality = models.CharField(_("nationality"), max_length=2, choices=NATIONALITIES, default="TH")

    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING, db_index=True)
    is_staff = models.BooleanField(default=False)
    email_verified_at = models.DateTimeField(null=True, blank=True)
    date_joined = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    objects = MemberManager()

    USERNAME_FIELD = "email"
    EMAIL_FIELD = "email"
    REQUIRED_FIELDS = ["full_name"]

    class Meta:
        verbose_name = _("member")
        verbose_name_plural = _("members")
        constraints = [
            models.UniqueConstraint(Lower("email"), name="member_email_ci_unique"),
            models.UniqueConstraint(fields=["country_code", "phone"], name="member_phone_unique"),
        ]

    def __str__(self):
        return self.email

    # Django uses is_active to allow or refuse login. Only suspension blocks
    # login; pending members may sign in and are sent to email verification.
    @property
    def is_active(self):
        return self.status != self.Status.SUSPENDED

    @property
    def is_verified(self):
        return self.status == self.Status.ACTIVE

    @property
    def display_phone(self):
        return f"{self.country_code} {self.phone}"

    def get_full_name(self):
        return self.full_name

    def get_short_name(self):
        return self.full_name.split(" ")[0] if self.full_name else self.email


class EmailOTP(models.Model):
    """A one-time code sent by email. Only a keyed hash of the code is stored."""

    class Purpose(models.TextChoices):
        REGISTER = "register", _("Registration")
        RESET = "reset", _("Password reset")

    member = models.ForeignKey(Member, on_delete=models.CASCADE, related_name="otps")
    purpose = models.CharField(max_length=10, choices=Purpose.choices)
    code_hash = models.CharField(max_length=64)
    expires_at = models.DateTimeField()
    attempts = models.PositiveSmallIntegerField(default=0)
    consumed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["member", "purpose", "-created_at"], name="otp_lookup_idx")]

    def __str__(self):
        return f"{self.purpose} OTP for member {self.member_id}"
