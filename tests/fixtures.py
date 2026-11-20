"""Fixtures shared by every app's tests."""

import importlib
from datetime import date
from io import BytesIO

import pytest
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image

PASSWORD = "Sapphire-Lounge-2026"


@pytest.fixture(autouse=True)
def _clear_cache():
    # Rate-limit counters live in the cache; keep tests independent.
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def make_member(db):
    from apps.accounts.models import Member

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


@pytest.fixture
def staff_user(make_member):
    return make_member(is_staff=True, full_name="Staff Person")


def make_image_bytes(color=(200, 30, 30), size=(320, 560), fmt="PNG"):
    buffer = BytesIO()
    Image.new("RGB", size, color).save(buffer, format=fmt)
    return buffer.getvalue()


@pytest.fixture
def slip_file():
    counter = {"n": 0}

    def _make(color=None):
        counter["n"] += 1
        # A different colour per call gives a different file hash.
        color = color or (counter["n"] * 20 % 255, 40, 90)
        return SimpleUploadedFile("slip.png", make_image_bytes(color), content_type="image/png")

    return _make


@pytest.fixture
def seal_tiers(db):
    """
    The tiers seeded by migration. Transactional tests flush the database
    between tests, so re-create them from the same data on demand.
    """
    from apps.memberships.models import SealTier

    seed = importlib.import_module("apps.memberships.migrations.0003_seed_seal_tiers")
    for tier in seed.TIERS:
        SealTier.objects.get_or_create(code=tier["code"], defaults=tier)
    return SealTier.objects.order_by("sort_order")


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
