"""Login with throttling, and password reset by email code."""

from django.conf import settings
from django.contrib.auth import authenticate
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext as _

from apps.core import ratelimit

from ..models import EmailOTP, Member
from ..selectors.member_selector import get_member_by_email
from . import otp_service

LOGIN_EMAIL_SCOPE = "login-email"
LOGIN_IP_SCOPE = "login-ip"
# An IP may try more addresses than a single email, but not unlimited.
IP_FAILURE_MULTIPLIER = 4


class LoginError(Exception):
    """User-safe login failure message."""


def _ip_limit():
    return settings.LOGIN_MAX_FAILURES * IP_FAILURE_MULTIPLIER


def authenticate_member(request, email: str, password: str, ip: str) -> Member:
    """
    Check credentials, enforcing per-email and per-IP failure limits.

    Returns the member (who may still be pending verification). Raises
    LoginError with a generic message so attackers cannot tell which part
    was wrong.
    """
    email_key = email.strip().lower()
    if ratelimit.is_limited(LOGIN_EMAIL_SCOPE, email_key, settings.LOGIN_MAX_FAILURES) or ratelimit.is_limited(
        LOGIN_IP_SCOPE, ip, _ip_limit()
    ):
        raise LoginError(_("Too many failed attempts. Please wait 15 minutes and try again."))

    member = authenticate(request, username=email_key, password=password)
    if member is None:
        ratelimit.hit(LOGIN_EMAIL_SCOPE, email_key, settings.LOGIN_LOCKOUT_SECONDS)
        ratelimit.hit(LOGIN_IP_SCOPE, ip, settings.LOGIN_LOCKOUT_SECONDS)
        # A suspended member with the right password also lands here, because
        # the auth backend refuses inactive accounts. Keep the message generic.
        raise LoginError(_("Incorrect email or password."))

    ratelimit.reset(LOGIN_EMAIL_SCOPE, email_key)
    return member


def request_password_reset(email: str) -> None:
    """
    Send a reset code if an eligible account exists.

    Always behaves the same from the caller's view (no account enumeration).
    Rate-limit errors are swallowed for the same reason.
    """
    member = get_member_by_email(email)
    if member is None or not member.is_active:
        return
    try:
        otp_service.issue(member, EmailOTP.Purpose.RESET)
    except otp_service.OTPError:
        return


def reset_password(email: str, code: str, new_password: str) -> Member:
    """
    Set a new password after a valid reset code. Raises OTPError on a bad code.

    A reset also proves ownership of the email, so a pending member is
    activated at the same time.
    """
    member = get_member_by_email(email)
    if member is None or not member.is_active:
        raise otp_service.OTPError(_("No active code. Please request a new one."))

    otp_service.verify(member, EmailOTP.Purpose.RESET, code)  # commits on its own
    with transaction.atomic():
        member.set_password(new_password)
        fields = ["password", "updated_at"]
        if member.status == Member.Status.PENDING:
            member.status = Member.Status.ACTIVE
            member.email_verified_at = timezone.now()
            fields += ["status", "email_verified_at"]
        member.save(update_fields=fields)
    ratelimit.reset(LOGIN_EMAIL_SCOPE, member.email)
    return member
