from datetime import timedelta

import pytest
from django.core import mail
from django.test import override_settings
from django.utils import timezone

from apps.accounts.models import EmailOTP
from apps.accounts.services import otp_service

from .conftest import last_code

pytestmark = pytest.mark.django_db(transaction=True)

REGISTER = EmailOTP.Purpose.REGISTER


def test_issue_sends_email_and_stores_only_a_hash(make_member):
    member = make_member()

    otp = otp_service.issue(member, REGISTER)

    code = last_code()
    assert mail.outbox[-1].to == [member.email]
    assert code not in otp.code_hash
    assert len(otp.code_hash) == 64
    assert "<" in mail.outbox[-1].alternatives[0][0]  # HTML part attached


def test_verify_accepts_correct_code_once(make_member):
    member = make_member()
    otp_service.issue(member, REGISTER)
    code = last_code()

    otp_service.verify(member, REGISTER, code)

    with pytest.raises(otp_service.OTPError):
        otp_service.verify(member, REGISTER, code)


def test_wrong_code_counts_attempts_and_burns_after_limit(make_member, settings):
    member = make_member()
    otp_service.issue(member, REGISTER)
    code = last_code()
    wrong = "000000" if code != "000000" else "111111"

    for _ in range(settings.OTP_MAX_ATTEMPTS - 1):
        with pytest.raises(otp_service.OTPError, match="attempts left"):
            otp_service.verify(member, REGISTER, wrong)
    with pytest.raises(otp_service.OTPError, match="Too many incorrect"):
        otp_service.verify(member, REGISTER, wrong)

    # Even the right code no longer works once burned.
    with pytest.raises(otp_service.OTPError, match="No active code"):
        otp_service.verify(member, REGISTER, code)
    assert EmailOTP.objects.get(member=member).attempts == settings.OTP_MAX_ATTEMPTS


def test_expired_code_is_rejected(make_member):
    member = make_member()
    otp = otp_service.issue(member, REGISTER)
    code = last_code()
    EmailOTP.objects.filter(pk=otp.pk).update(expires_at=timezone.now() - timedelta(seconds=1))

    with pytest.raises(otp_service.OTPError, match="expired"):
        otp_service.verify(member, REGISTER, code)


def test_new_code_invalidates_previous_one(make_member):
    member = make_member()
    otp_service.issue(member, REGISTER)
    first = last_code()
    otp_service.issue(member, REGISTER)
    second = last_code()

    if first != second:
        with pytest.raises(otp_service.OTPError):
            otp_service.verify(member, REGISTER, first)
    otp_service.verify(member, REGISTER, second)


@override_settings(OTP_MAX_SENDS=2)
def test_sending_is_rate_limited(make_member):
    member = make_member()
    otp_service.issue(member, REGISTER)
    otp_service.issue(member, REGISTER)

    with pytest.raises(otp_service.OTPError, match="Too many codes"):
        otp_service.issue(member, REGISTER)
    assert len(mail.outbox) == 2


def test_codes_are_purpose_specific(make_member):
    member = make_member()
    otp_service.issue(member, REGISTER)
    code = last_code()

    with pytest.raises(otp_service.OTPError):
        otp_service.verify(member, EmailOTP.Purpose.RESET, code)
