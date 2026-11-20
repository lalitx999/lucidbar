from datetime import timedelta

import pytest
from django.utils import timezone

from apps.payments.clients.easyslip import EasySlipResult
from apps.payments.services import slip_decision as sd

START = timezone.now()


def ok_result(**overrides):
    raw = {
        "transRef": "68370160657749I376388B35",
        "date": (START + timedelta(minutes=5)).isoformat(),
        "amount": {"amount": 499.00},
        "receiver": {"account": {"bank": {"type": "BANKAC", "account": "xxx-x-x3743-x"}}},
    }
    raw.update(overrides.pop("raw", {}))
    data = {
        "isDuplicate": False,
        "matchedAccount": None,
        "isAmountMatched": True,
        "amountInSlip": 499.0,
        "rawSlip": raw,
    }
    data.update(overrides)
    return EasySlipResult(ok=True, data=data)


def decide(result, used=False, expected=49900):
    return sd.decide(result=result, expected_satang=expected, checkout_started=START, trans_ref_used=used)


# masked account comparison -------------------------------------------------
@pytest.mark.parametrize(
    "masked, real, expected",
    [
        # 7811737430 is written 781-1-73743-0, so slips show the middle digits.
        ("xxx-x-x3743-x", "7811737430", True),
        ("781-1-xxxxx-0", "7811737430", True),
        ("xxx-x-x7430-x", "7811737430", False),  # "ends with 7430" is not a match
        ("xxx-x-x3744-x", "7811737430", False),  # one visible digit differs
        ("xxx-x-xx743-x", "7811737430", False),  # only 3 visible digits
        ("xxx-x-x7430", "7811737430", False),  # length differs
        ("", "7811737430", False),
        ("08xxxxxxxx78", "0812345678", False),  # wrong length for 10-digit
        ("08xxxxx678", "0812345678", True),
    ],
)
def test_masked_matches(masked, real, expected):
    assert sd.masked_matches(masked, real) is expected


# decisions -----------------------------------------------------------------
def test_clean_slip_is_approved():
    decision = decide(ok_result())

    assert decision.action == sd.APPROVE
    assert decision.trans_ref == "68370160657749I376388B35"
    assert decision.amount_satang == 49900


def test_matched_account_from_easyslip_is_enough():
    result = ok_result(matchedAccount={"bankNumber": "xxx"}, raw={"receiver": {}})

    assert decide(result).action == sd.APPROVE


def test_promptpay_proxy_receiver_is_accepted():
    receiver = {"account": {"proxy": {"type": "MSISDN", "account": "08xxxxx678"}}}

    assert decide(ok_result(raw={"receiver": receiver})).action == sd.APPROVE


def test_unknown_receiver_goes_to_review():
    receiver = {"account": {"bank": {"type": "BANKAC", "account": "xxx-x-x9999-x"}}}

    decision = decide(ok_result(raw={"receiver": receiver}))

    assert decision.action == sd.REVIEW


def test_wrong_amount_asks_for_new_slip():
    decision = decide(ok_result(raw={"amount": {"amount": 490.00}}, isAmountMatched=False))

    assert decision.action == sd.RETRY_UPLOAD
    assert "499.00" in decision.reason


def test_reused_trans_ref_is_refused():
    assert decide(ok_result(), used=True).action == sd.RETRY_UPLOAD


def test_easyslip_duplicate_unknown_to_us_goes_to_review():
    assert decide(ok_result(isDuplicate=True)).action == sd.REVIEW


def test_old_slip_goes_to_review():
    old = (START - timedelta(hours=3)).isoformat()

    assert decide(ok_result(raw={"date": old})).action == sd.REVIEW


def test_slip_within_grace_before_checkout_is_ok():
    shortly_before = (START - timedelta(minutes=10)).isoformat()

    assert decide(ok_result(raw={"date": shortly_before})).action == sd.APPROVE


def test_missing_trans_ref_goes_to_review():
    assert decide(ok_result(raw={"transRef": ""})).action == sd.REVIEW


def test_unreadable_slip_asks_for_new_upload():
    result = EasySlipResult(ok=False, code="SLIP_NOT_FOUND")

    assert decide(result).action == sd.RETRY_UPLOAD


@pytest.mark.parametrize("code", ["QUOTA_EXCEEDED", "INVALID_API_KEY", "DISABLED"])
def test_account_or_config_problems_go_to_review(code):
    assert decide(EasySlipResult(ok=False, code=code)).action == sd.REVIEW


def test_satang_conversion_avoids_float_error():
    # 0.1 + 0.2 style float problems must not reject a correct payment.
    assert decide(ok_result(raw={"amount": {"amount": 1234.56}}), expected=123456).action == sd.APPROVE
