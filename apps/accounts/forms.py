import re
from datetime import date

from django import forms
from django.conf import settings
from django.contrib.auth import password_validation
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from .constants import COUNTRY_DIAL_CODES, NATIONALITIES
from .models import Member
from .selectors import member_selector

PHONE_RE = re.compile(r"^\d{6,15}$")


def age_on(dob: date, today: date) -> int:
    return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))


def clean_phone_value(value: str) -> str:
    """Keep digits only and drop a leading trunk zero (081... -> 81...)."""
    digits = re.sub(r"\D", "", value or "")
    if digits.startswith("0"):
        digits = digits[1:]
    if not PHONE_RE.match(digits):
        raise forms.ValidationError(_("Enter a valid mobile number."))
    return digits


class LucidFormMixin:
    """Apply the dark Lucid input styling to every widget."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            widget = field.widget
            base = "form-select" if isinstance(widget, forms.Select) else "form-control"
            if isinstance(widget, forms.CheckboxInput):
                base = "form-check-input"
            widget.attrs["class"] = f"{base} lucid-input {widget.attrs.get('class', '')}".strip()


class RegistrationForm(LucidFormMixin, forms.Form):
    full_name = forms.CharField(
        label=_("Full name"), max_length=150, widget=forms.TextInput(attrs={"autocomplete": "name"})
    )
    email = forms.EmailField(label=_("Email"), widget=forms.EmailInput(attrs={"autocomplete": "email"}))
    country_code = forms.ChoiceField(label=_("Code"), choices=COUNTRY_DIAL_CODES, initial="+66")
    phone = forms.CharField(
        label=_("Mobile number"),
        max_length=20,
        widget=forms.TextInput(attrs={"inputmode": "tel", "autocomplete": "tel-national"}),
    )
    date_of_birth = forms.DateField(
        label=_("Date of birth"), widget=forms.DateInput(attrs={"type": "date", "autocomplete": "bday"})
    )
    nationality = forms.ChoiceField(label=_("Nationality"), choices=NATIONALITIES, initial="TH")
    password = forms.CharField(
        label=_("Password"), strip=False, widget=forms.PasswordInput(attrs={"autocomplete": "new-password"})
    )
    password_confirm = forms.CharField(
        label=_("Confirm password"), strip=False, widget=forms.PasswordInput(attrs={"autocomplete": "new-password"})
    )
    accept_terms = forms.BooleanField(
        label=_("I confirm I am at least 20 years old and accept the membership rules and privacy notice.")
    )

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if member_selector.email_exists(email):
            raise forms.ValidationError(_("An account with this email already exists."))
        return email

    def clean_phone(self):
        return clean_phone_value(self.cleaned_data["phone"])

    def clean_date_of_birth(self):
        dob = self.cleaned_data["date_of_birth"]
        today = timezone.localdate()
        if dob > today:
            raise forms.ValidationError(_("Enter a valid date of birth."))
        if age_on(dob, today) < settings.MINIMUM_AGE:
            raise forms.ValidationError(
                _("Membership is limited to guests aged %(age)d and over.") % {"age": settings.MINIMUM_AGE}
            )
        return dob

    def clean(self):
        data = super().clean()
        if data.get("phone") and data.get("country_code"):
            if member_selector.phone_exists(data["country_code"], data["phone"]):
                self.add_error("phone", _("This mobile number is already registered."))
        password, confirm = data.get("password"), data.get("password_confirm")
        if password and confirm and password != confirm:
            self.add_error("password_confirm", _("Passwords do not match."))
        if password:
            # Build an unsaved member so similarity checks can compare against name/email.
            probe = Member(email=data.get("email", ""), full_name=data.get("full_name", ""))
            try:
                password_validation.validate_password(password, probe)
            except forms.ValidationError as exc:
                self.add_error("password", exc)
        return data


class OTPForm(LucidFormMixin, forms.Form):
    code = forms.CharField(
        label=_("Verification code"),
        min_length=6,
        max_length=6,
        widget=forms.TextInput(
            attrs={
                "inputmode": "numeric",
                "autocomplete": "one-time-code",
                "pattern": "[0-9]{6}",
                "class": "otp-input",
            }
        ),
    )

    def clean_code(self):
        code = self.cleaned_data["code"].strip()
        if not code.isdigit():
            raise forms.ValidationError(_("The code is 6 digits."))
        return code


class LoginForm(LucidFormMixin, forms.Form):
    email = forms.EmailField(label=_("Email"), widget=forms.EmailInput(attrs={"autocomplete": "email"}))
    password = forms.CharField(
        label=_("Password"), strip=False, widget=forms.PasswordInput(attrs={"autocomplete": "current-password"})
    )


class PasswordResetRequestForm(LucidFormMixin, forms.Form):
    email = forms.EmailField(label=_("Email"), widget=forms.EmailInput(attrs={"autocomplete": "email"}))


class SetPasswordMixin:
    """Shared new-password checks: confirmation match and Django validators."""

    def clean(self):
        data = super().clean()
        password, confirm = data.get("new_password"), data.get("new_password_confirm")
        if password and confirm and password != confirm:
            self.add_error("new_password_confirm", _("Passwords do not match."))
        if password:
            try:
                password_validation.validate_password(password, getattr(self, "member", None))
            except forms.ValidationError as exc:
                self.add_error("new_password", exc)
        return data


class PasswordResetConfirmForm(SetPasswordMixin, OTPForm):
    new_password = forms.CharField(
        label=_("New password"), strip=False, widget=forms.PasswordInput(attrs={"autocomplete": "new-password"})
    )
    new_password_confirm = forms.CharField(
        label=_("Confirm new password"),
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
    )


class ProfileForm(LucidFormMixin, forms.Form):
    full_name = forms.CharField(label=_("Full name"), max_length=150)
    country_code = forms.ChoiceField(label=_("Code"), choices=COUNTRY_DIAL_CODES)
    phone = forms.CharField(label=_("Mobile number"), max_length=20, widget=forms.TextInput(attrs={"inputmode": "tel"}))
    nationality = forms.ChoiceField(label=_("Nationality"), choices=NATIONALITIES)

    def __init__(self, *args, member, **kwargs):
        self.member = member
        kwargs.setdefault(
            "initial",
            {
                "full_name": member.full_name,
                "country_code": member.country_code,
                "phone": member.phone,
                "nationality": member.nationality,
            },
        )
        super().__init__(*args, **kwargs)

    def clean_phone(self):
        return clean_phone_value(self.cleaned_data["phone"])

    def clean(self):
        data = super().clean()
        if data.get("phone") and data.get("country_code"):
            if member_selector.phone_exists(data["country_code"], data["phone"], exclude_pk=self.member.pk):
                self.add_error("phone", _("This mobile number is already registered."))
        return data


class ChangePasswordForm(SetPasswordMixin, LucidFormMixin, forms.Form):
    current_password = forms.CharField(
        label=_("Current password"),
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "current-password"}),
    )
    new_password = forms.CharField(
        label=_("New password"), strip=False, widget=forms.PasswordInput(attrs={"autocomplete": "new-password"})
    )
    new_password_confirm = forms.CharField(
        label=_("Confirm new password"),
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
    )

    def __init__(self, *args, member, **kwargs):
        self.member = member
        super().__init__(*args, **kwargs)

    def clean_current_password(self):
        value = self.cleaned_data["current_password"]
        if not self.member.check_password(value):
            raise forms.ValidationError(_("Your current password is incorrect."))
        return value
