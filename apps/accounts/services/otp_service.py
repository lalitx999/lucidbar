"""
Email one-time codes: issue, send (via Celery), verify.

Security notes:
- Codes come from `secrets`, and only an HMAC of the code is stored.
- Each code allows OTP_MAX_ATTEMPTS guesses, then it is burned.
- Sending is limited to OTP_MAX_SENDS per email per window.
- Issuing a new code invalidates any older unused code for the same purpose.
"""

import hashlib
import hmac
import secrets
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext as _

from apps.core import ratelimit
from apps.notifications.tasks import send_templated_email

from ..models import EmailOTP, Member

SEND_SCOPE = "otp-send"


class OTPError(Exception):
    """Raised when a code cannot be issued or verified. The message is user-safe."""


def _hash(member_id, purpose, code):
    message = f"{member_id}:{purpose}:{code}".encode()
    return hmac.new(settings.SECRET_KEY.encode(), message, hashlib.sha256).hexdigest()


def _generate_code():
    return f"{secrets.randbelow(10**settings.OTP_LENGTH):0{settings.OTP_LENGTH}d}"


def can_send(email):
    return not ratelimit.is_limited(SEND_SCOPE, email.lower(), settings.OTP_MAX_SENDS)


def issue(member: Member, purpose: str) -> EmailOTP:
    """
    Create a new code for the member and queue the email.

    Raises OTPError if the member has requested too many codes recently.
    """
    if not can_send(member.email):
        raise OTPError(_("Too many codes requested. Please wait a few minutes and try again."))

    code = _generate_code()
    now = timezone.now()
    with transaction.atomic():
        # Invalidate older unused codes so only the newest one works.
        EmailOTP.objects.filter(member=member, purpose=purpose, consumed_at__isnull=True).update(consumed_at=now)
        otp = EmailOTP.objects.create(
            member=member,
            purpose=purpose,
            code_hash=_hash(member.pk, purpose, code),
            expires_at=now + timedelta(seconds=settings.OTP_TTL_SECONDS),
        )
        ratelimit.hit(SEND_SCOPE, member.email.lower(), settings.OTP_SEND_WINDOW_SECONDS)

        subject = {
            EmailOTP.Purpose.REGISTER: _("Your Lucid Society verification code"),
            EmailOTP.Purpose.RESET: _("Your Lucid Society password reset code"),
        }[purpose]
        context = {
            "name": member.get_short_name(),
            "code": code,
            "minutes": settings.OTP_TTL_SECONDS // 60,
            "purpose": purpose,
        }
        # Queue only after the code is committed, so the worker never races the DB.
        transaction.on_commit(
            lambda: send_templated_email.delay(
                to=member.email,
                subject=str(subject),
                template="emails/otp",
                context=context,
            )
        )
    return otp


def verify(member: Member, purpose: str, code: str) -> None:
    """
    Check a code and mark it used. Raises OTPError with a user-safe message.

    The row is locked so two parallel submissions cannot both succeed or both
    slip past the attempt limit.
    """
    code = (code or "").strip()
    with transaction.atomic():
        otp = (
            EmailOTP.objects.select_for_update()
            .filter(member=member, purpose=purpose, consumed_at__isnull=True)
            .order_by("-created_at")
            .first()
        )
        if otp is None:
            raise OTPError(_("No active code. Please request a new one."))

        now = timezone.now()
        if otp.expires_at <= now:
            otp.consumed_at = now
            otp.save(update_fields=["consumed_at"])
            raise OTPError(_("This code has expired. Please request a new one."))

        if not hmac.compare_digest(otp.code_hash, _hash(member.pk, purpose, code)):
            otp.attempts += 1
            fields = ["attempts"]
            if otp.attempts >= settings.OTP_MAX_ATTEMPTS:
                otp.consumed_at = now
                fields.append("consumed_at")
            otp.save(update_fields=fields)
        else:
            otp.consumed_at = now
            otp.save(update_fields=["consumed_at"])
            return

    # Outside the atomic block so the failed-attempt update is committed.
    if otp.consumed_at:
        raise OTPError(_("Too many incorrect attempts. Please request a new code."))
    remaining = settings.OTP_MAX_ATTEMPTS - otp.attempts
    raise OTPError(_("Incorrect code. %(remaining)d attempts left.") % {"remaining": remaining})
