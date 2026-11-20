"""Member registration and email verification."""

import secrets
from dataclasses import dataclass
from datetime import date

from django.db import IntegrityError, transaction
from django.utils import timezone

from ..models import EmailOTP, Member
from . import otp_service

HANDLE_ALPHABET = "abcdefghjkmnpqrstuvwxyz23456789"  # no look-alike characters


@dataclass(frozen=True)
class RegistrationData:
    full_name: str
    email: str
    country_code: str
    phone: str
    date_of_birth: date
    nationality: str
    password: str


def _new_handle():
    return "lucid_" + "".join(secrets.choice(HANDLE_ALPHABET) for _ in range(6))


def _create_with_unique_handle(data: RegistrationData) -> Member:
    for _attempt in range(5):
        handle = _new_handle()
        try:
            with transaction.atomic():  # savepoint, so a handle clash can be retried
                return Member.objects.create_user(
                    email=data.email,
                    password=data.password,
                    full_name=data.full_name.strip(),
                    handle=handle,
                    country_code=data.country_code,
                    phone=data.phone,
                    date_of_birth=data.date_of_birth,
                    nationality=data.nationality,
                    status=Member.Status.PENDING,
                )
        except IntegrityError:
            # Retry only for a handle clash; email/phone clashes must surface.
            if not Member.objects.filter(handle=handle).exists():
                raise
    raise RuntimeError("Could not allocate a unique member handle")


def register_member(data: RegistrationData) -> Member:
    """
    Create a pending member and email a verification code.

    Validation (age, uniqueness, password strength) is done by the form; the
    database constraints are the final guard against races.
    """
    with transaction.atomic():
        member = _create_with_unique_handle(data)
        otp_service.issue(member, EmailOTP.Purpose.REGISTER)
    return member


def resend_verification(member: Member) -> None:
    otp_service.issue(member, EmailOTP.Purpose.REGISTER)


def verify_email(member: Member, code: str) -> Member:
    """
    Confirm the registration code and activate the member.

    Raises otp_service.OTPError on a bad code. Later phases hook the Bronze
    membership and signup keys into this transaction.
    """
    # verify() commits on its own: a failed attempt must be recorded even
    # though it raises, so it must not run inside an outer transaction.
    otp_service.verify(member, EmailOTP.Purpose.REGISTER, code)
    with transaction.atomic():
        member.status = Member.Status.ACTIVE
        member.email_verified_at = timezone.now()
        member.save(update_fields=["status", "email_verified_at", "updated_at"])
    return member
