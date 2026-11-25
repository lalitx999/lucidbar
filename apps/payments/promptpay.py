"""
PromptPay QR payload (EMVCo merchant-presented QR, Thai PromptPay profile)
and SVG rendering.
"""

import re

from apps.core import qr

PROMPTPAY_AID = "A000000677010111"


def _tlv(tag: str, value: str) -> str:
    return f"{tag}{len(value):02d}{value}"


def crc16_ccitt(data: str) -> str:
    crc = 0xFFFF
    for byte in data.encode("ascii"):
        crc ^= byte << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) if crc & 0x8000 else (crc << 1)
            crc &= 0xFFFF
    return f"{crc:04X}"


def build_payload(promptpay_id: str, amount_satang: int | None = None) -> str:
    """
    Build the QR text for a mobile number (10 digits) or tax/national ID
    (13 digits). With an amount, the QR is single-use style (point of
    initiation 12) and banking apps pre-fill the exact amount.
    """
    digits = re.sub(r"\D", "", promptpay_id or "")
    if len(digits) == 13:
        target = _tlv("02", digits)
    elif len(digits) == 10 and digits.startswith("0"):
        target = _tlv("01", "0066" + digits[1:])
    else:
        raise ValueError("PromptPay ID must be a 10-digit mobile number or a 13-digit ID")

    merchant = _tlv("00", PROMPTPAY_AID) + target
    parts = [
        _tlv("00", "01"),
        _tlv("01", "12" if amount_satang else "11"),
        _tlv("29", merchant),
        _tlv("53", "764"),  # THB
    ]
    if amount_satang:
        parts.append(_tlv("54", f"{amount_satang / 100:.2f}"))
    parts.append(_tlv("58", "TH"))
    body = "".join(parts) + "6304"
    return body + crc16_ccitt(body)


def render_svg(payload: str) -> str:
    """Kept for callers in this app; the renderer lives in apps.core.qr."""
    return qr.render_svg(payload)
