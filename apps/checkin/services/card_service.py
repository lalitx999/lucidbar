"""
The member's QR identity card.

The QR holds a signed, timestamped token (django.core.signing), not the raw
member ID. A token is only accepted for CHECKIN_CARD_MAX_AGE_SECONDS, so a
screenshot passed to someone else stops working within minutes. The member's
Identity page fetches a fresh card before the old one expires.
"""

from django.conf import settings
from django.core import signing
from django.utils.translation import gettext as _

SALT = "lucid.identity-card.v1"
PREFIX = "LUCID1."


class CardError(Exception):
    """User-safe message, shown to door staff."""


def make_token(member) -> str:
    return PREFIX + signing.dumps({"m": member.pk}, salt=SALT, compress=True)


def read_token(token: str) -> int:
    """Return the member ID in a valid, unexpired card token."""
    token = (token or "").strip()
    if not token.startswith(PREFIX):
        raise CardError(_("This is not a Lucid identity card."))
    try:
        data = signing.loads(token[len(PREFIX) :], salt=SALT, max_age=settings.CHECKIN_CARD_MAX_AGE_SECONDS)
    except signing.SignatureExpired as exc:
        raise CardError(_("This card has expired. Ask the member to refresh their Identity page.")) from exc
    except signing.BadSignature as exc:
        raise CardError(_("This is not a Lucid identity card.")) from exc
    member_id = data.get("m") if isinstance(data, dict) else None
    if not isinstance(member_id, int):
        raise CardError(_("This is not a Lucid identity card."))
    return member_id
