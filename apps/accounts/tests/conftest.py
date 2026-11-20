import re
from datetime import date

import pytest
from django.core import mail
from django.core.cache import cache

from apps.accounts.models import Member

PASSWORD = "Sapphire-Lounge-2026"


@pytest.fixture(autouse=True)
def _clear_cache():
    # Rate-limit counters live in the cache; keep tests independent.
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def registration_payload():
    return {
        "full_name": "Arthur Pendleton",
        "email": "Arthur@Example.com",
        "country_code": "+66",
        "phone": "0812345678",
        "date_of_birth": "1990-05-17",
        "nationality": "GB",
        "password": PASSWORD,
        "password_confirm": PASSWORD,
        "accept_terms": "on",
    }


@pytest.fixture
def make_member(db):
    counter = {"n": 0}

    def _make(status=Member.Status.ACTIVE, email=None, **extra):
        counter["n"] += 1
        n = counter["n"]
        extra.setdefault("full_name", f"Member {n}")
        extra.setdefault("handle", f"lucid_test{n:02d}")
        extra.setdefault("phone", f"81000000{n:02d}")
        extra.setdefault("date_of_birth", date(1990, 1, 1))
        return Member.objects.create_user(
            email=email or f"member{n}@example.com", password=PASSWORD, status=status, **extra
        )

    return _make


def last_code():
    """Pull the 6-digit code out of the most recent email."""
    assert mail.outbox, "no email was sent"
    match = re.search(r"\b(\d{6})\b", mail.outbox[-1].body)
    assert match, "no code in email body"
    return match.group(1)
