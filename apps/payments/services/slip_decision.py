"""
Decide what to do with an EasySlip result. Pure functions, no database.

Rule of thumb: approve automatically only when every check passes clearly.
Anything ambiguous goes to staff review rather than being approved.
"""

import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.utils.dateparse import parse_datetime
from django.utils.translation import gettext as _

APPROVE = "approve"
RETRY_UPLOAD = "retry_upload"  # the slip is unusable; member uploads another
REVIEW = "review"  # staff must look

MIN_VISIBLE_DIGITS = 4


@dataclass(frozen=True)
class Decision:
    action: str
    reason: str = ""  # shown to staff (and to the member for RETRY_UPLOAD)
    trans_ref: str = ""
    amount_satang: int | None = None
    slip_date: datetime | None = None


def masked_matches(masked: str, real: str) -> bool:
    """
    Compare a masked number from a slip (for example "xxx-x-x7430-x") with
    our real number, position by position. Every visible digit must match,
    lengths must match, and at least MIN_VISIBLE_DIGITS digits must be visible.
    """
    masked_clean = re.sub(r"[^0-9xX*]", "", masked or "").lower().replace("*", "x")
    real_clean = re.sub(r"\D", "", real or "")
    if not masked_clean or not real_clean or len(masked_clean) != len(real_clean):
        return False
    visible = 0
    for m, r in zip(masked_clean, real_clean, strict=True):
        if m == "x":
            continue
        if m != r:
            return False
        visible += 1
    return visible >= MIN_VISIBLE_DIGITS


def _promptpay_candidates(promptpay_id: str) -> list[str]:
    digits = re.sub(r"\D", "", promptpay_id or "")
    if not digits:
        return []
    candidates = [digits]
    if len(digits) == 10 and digits.startswith("0"):
        candidates.append("66" + digits[1:])  # some slips show the international form
    return candidates


def receiver_matches(data: dict) -> bool:
    """True if the slip clearly shows money arriving at one of our accounts."""
    if data.get("matchedAccount"):
        return True  # EasySlip matched it against accounts registered in our EasySlip dashboard

    account = ((data.get("rawSlip") or {}).get("receiver") or {}).get("account") or {}
    bank_ac = (account.get("bank") or {}).get("account", "")
    proxy_ac = (account.get("proxy") or {}).get("account", "")

    if bank_ac and masked_matches(bank_ac, settings.PAYMENT_BANK_ACCOUNT_NUMBER):
        return True
    return any(proxy_ac and masked_matches(proxy_ac, c) for c in _promptpay_candidates(settings.PROMPTPAY_ID))


def _to_satang(value) -> int | None:
    try:
        return int((Decimal(str(value)) * 100).quantize(Decimal("1")))
    except (InvalidOperation, TypeError, ValueError):
        return None


def decide(*, result, expected_satang: int, checkout_started: datetime, trans_ref_used: bool) -> Decision:
    """
    result: EasySlipResult. trans_ref_used: whether our database already has
    this bank reference on another slip (checked by the caller).
    """
    if not result.ok:
        if result.is_bad_slip:
            return Decision(
                RETRY_UPLOAD, _("We could not read this slip. Please upload a clear screenshot of the slip.")
            )
        # Disabled, auth/quota problems, unknown errors: a person decides.
        return Decision(REVIEW, f"EasySlip: {result.code}")

    data = result.data
    raw = data.get("rawSlip") or {}
    trans_ref = str(raw.get("transRef") or "").strip()
    amount = _to_satang((raw.get("amount") or {}).get("amount", data.get("amountInSlip")))
    slip_date = parse_datetime(raw.get("date") or "") if raw.get("date") else None
    common = {"trans_ref": trans_ref, "amount_satang": amount, "slip_date": slip_date}

    if not trans_ref:
        return Decision(REVIEW, "Slip has no transaction reference", **common)
    if trans_ref_used:
        return Decision(RETRY_UPLOAD, _("This slip has already been used."), **common)
    if amount != expected_satang or data.get("isAmountMatched") is False:
        return Decision(
            RETRY_UPLOAD,
            _("The amount on the slip does not match. Please transfer exactly %(amount).2f THB.")
            % {"amount": expected_satang / 100},
            **common,
        )
    if not receiver_matches(data):
        return Decision(REVIEW, "Receiver account could not be confirmed", **common)
    if data.get("isDuplicate"):
        # Verified before but unknown to us (another branch or an older system).
        return Decision(REVIEW, "EasySlip reports this slip was verified before", **common)
    if slip_date is None:
        return Decision(REVIEW, "Slip date missing", **common)
    if slip_date < checkout_started - timedelta(minutes=settings.SLIP_DATE_GRACE_MINUTES):
        return Decision(REVIEW, "Slip is older than the checkout", **common)

    return Decision(APPROVE, "", **common)
