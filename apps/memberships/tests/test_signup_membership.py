import pytest
from django.urls import reverse

from apps.accounts.models import Member
from apps.accounts.tests.conftest import last_code
from apps.memberships.models import Membership
from apps.memberships.selectors import membership_selector
from apps.memberships.services import membership_service

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.usefixtures("seal_tiers")]


def test_email_verification_grants_bronze(client, registration_payload):
    client.post(reverse("accounts:register"), registration_payload)
    client.post(reverse("accounts:verify"), {"code": last_code()})

    member = Member.objects.get()
    current = membership_selector.current_membership(member)
    assert current.tier.code == "bronze"
    assert current.ends_at is None
    assert current.source == Membership.Source.SIGNUP


def test_signup_grant_is_idempotent(make_member):
    member = make_member()

    membership_service.grant_signup_membership(member)
    membership_service.grant_signup_membership(member)

    assert Membership.objects.filter(member=member).count() == 1


def test_portal_shows_current_seal(client, make_member):
    member = make_member()
    membership_service.grant_signup_membership(member)
    client.force_login(member)

    html = client.get(reverse("core:portal")).content.decode()

    assert "Bronze Seal" in html
    assert reverse("payments:choose_seal") in html


def test_bronze_grant_credits_welcome_keys(make_member):
    from apps.keys.selectors import keys_selector

    member = make_member()
    membership_service.grant_signup_membership(member)
    membership_service.grant_signup_membership(member)

    assert keys_selector.balance_of(member) == 2  # once, not twice
