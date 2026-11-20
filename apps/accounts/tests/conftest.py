import re

from django.core import mail

from tests.fixtures import PASSWORD  # noqa: F401 (re-exported for account tests)


def last_code():
    """Pull the 6-digit code out of the most recent email."""
    assert mail.outbox, "no email was sent"
    match = re.search(r"\b(\d{6})\b", mail.outbox[-1].body)
    assert match, "no code in email body"
    return match.group(1)
