"""
EasySlip API v2 client (POST /v2/verify/bank with a multipart image).

Only network/transport concerns live here. Deciding whether a slip is
acceptable is done by services/slip_decision.py.
"""

import hashlib
import logging
from dataclasses import dataclass, field

import requests
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)

# Errors worth retrying later: rate limit, provider outage, Bangkok Bank's
# 5-minute delay before a fresh slip can be read.
TEMPORARY_CODES = {"RATE_LIMIT_EXCEEDED", "API_SERVER_ERROR", "INTERNAL_SERVER_ERROR", "SLIP_PENDING"}
# The image itself is the problem: ask the member for a clearer slip.
BAD_SLIP_CODES = {"SLIP_NOT_FOUND", "INVALID_IMAGE_FORMAT", "IMAGE_SIZE_TOO_LARGE", "VALIDATION_ERROR"}


class EasySlipTemporaryError(Exception):
    """Try again later. `retry_after` is a hint in seconds, if known."""

    def __init__(self, message, retry_after=None):
        super().__init__(message)
        self.retry_after = retry_after


@dataclass(frozen=True)
class EasySlipResult:
    ok: bool
    code: str = ""
    message: str = ""
    data: dict = field(default_factory=dict)

    @property
    def is_bad_slip(self):
        return not self.ok and self.code in BAD_SLIP_CODES


def verify_slip(image: bytes, amount_satang: int) -> EasySlipResult:
    """
    Send the slip to EasySlip. Returns a result for definite answers and
    raises EasySlipTemporaryError for anything that should be retried.
    """
    mode = settings.EASYSLIP_MODE
    if mode == "fake":
        return _fake_result(image, amount_satang)
    if mode != "live":
        return EasySlipResult(ok=False, code="DISABLED", message="Automatic verification is turned off")

    try:
        response = requests.post(
            settings.EASYSLIP_URL,
            headers={"Authorization": f"Bearer {settings.EASYSLIP_API_KEY}"},
            files={"image": ("slip.jpg", image, "image/jpeg")},
            data={
                "matchAmount": f"{amount_satang / 100:.2f}",
                "matchAccount": "true",
                "checkDuplicate": "true",
            },
            timeout=settings.EASYSLIP_TIMEOUT_SECONDS,
        )
    except requests.RequestException as exc:
        raise EasySlipTemporaryError(f"network error: {type(exc).__name__}") from exc

    try:
        body = response.json()
    except ValueError:
        body = {}

    if response.status_code == 200 and body.get("success"):
        return EasySlipResult(ok=True, data=body.get("data") or {}, message=body.get("message", ""))

    error = body.get("error") or {}
    code = error.get("code") or f"HTTP_{response.status_code}"
    message = error.get("message", "")
    if code in TEMPORARY_CODES or response.status_code >= 500 or response.status_code == 429:
        retry_after = response.headers.get("Retry-After")
        raise EasySlipTemporaryError(code, retry_after=int(retry_after) if (retry_after or "").isdigit() else None)

    if response.status_code in (401, 403):
        # Our configuration or account (key, quota, IP) is wrong. Staff must look.
        logger.error("EasySlip refused our request: %s %s", response.status_code, code)
    return EasySlipResult(ok=False, code=code, message=message)


def _fake_result(image: bytes, amount_satang: int) -> EasySlipResult:
    """Local development only: pretend the slip is valid and paid to us."""
    digest = hashlib.sha256(image).hexdigest()[:20].upper()
    amount = amount_satang / 100
    return EasySlipResult(
        ok=True,
        message="Fake verification (local development)",
        data={
            "isDuplicate": False,
            "matchedAccount": {"nameEn": settings.PAYMENT_BANK_ACCOUNT_NAME, "bankNumber": "fake"},
            "amountInOrder": amount,
            "amountInSlip": amount,
            "isAmountMatched": True,
            "rawSlip": {
                "transRef": f"FAKE{digest}",
                "date": timezone.now().isoformat(),
                "amount": {"amount": amount},
                "receiver": {"account": {"bank": {"type": "BANKAC", "account": "xxx-x-x0000-x"}}},
            },
        },
    )
