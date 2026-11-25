import pytest
from django.urls import reverse

from apps.accounts.models import Member

from .conftest import PASSWORD

pytestmark = pytest.mark.django_db


def test_portal_requires_login(client):
    response = client.get(reverse("core:portal"))

    assert response.status_code == 302
    assert response["Location"].startswith(reverse("accounts:login"))


def test_unverified_signed_in_member_is_sent_to_verify(client, make_member):
    member = make_member(status=Member.Status.PENDING)
    client.force_login(member)

    response = client.get(reverse("core:portal"))

    assert response["Location"] == reverse("accounts:verify")


def test_portal_shows_tab_bar_and_handle(client, make_member):
    member = make_member()
    client.force_login(member)

    response = client.get(reverse("core:portal"))

    html = response.content.decode()
    assert response.status_code == 200
    assert f"@{member.handle}" in html
    assert 'class="tabbar"' in html
    assert "no-cache" in response["Cache-Control"]


def test_welcome_redirects_signed_in_member(client, make_member):
    client.force_login(make_member())

    response = client.get(reverse("core:welcome"))

    assert response["Location"] == reverse("core:portal")


def test_identity_update_changes_editable_fields_only(client, make_member):
    member = make_member()
    client.force_login(member)

    response = client.post(
        reverse("accounts:identity"),
        {"full_name": "New Name", "country_code": "+44", "phone": "07700900123", "nationality": "GB"},
    )

    assert response["Location"] == reverse("accounts:identity")
    member.refresh_from_db()
    assert (member.full_name, member.country_code, member.phone, member.nationality) == (
        "New Name",
        "+44",
        "7700900123",
        "GB",
    )


def test_identity_rejects_phone_of_another_member(client, make_member):
    other = make_member()
    member = make_member()
    client.force_login(member)

    response = client.post(
        reverse("accounts:identity"),
        {"full_name": "X", "country_code": other.country_code, "phone": other.phone, "nationality": "TH"},
    )

    assert response.status_code == 200
    assert "already registered" in response.content.decode()


def test_change_password_keeps_session(client, make_member):
    member = make_member()
    client.force_login(member)
    new_password = "Velvet-Chamber-9931"

    response = client.post(
        reverse("accounts:change_password"),
        {"current_password": PASSWORD, "new_password": new_password, "new_password_confirm": new_password},
    )

    assert response["Location"] == reverse("accounts:identity")
    member.refresh_from_db()
    assert member.check_password(new_password)
    assert client.get(reverse("core:portal")).status_code == 200


def test_change_password_requires_current_password(client, make_member):
    member = make_member()
    client.force_login(member)

    response = client.post(
        reverse("accounts:change_password"),
        {
            "current_password": "nope",
            "new_password": "Velvet-Chamber-9931",
            "new_password_confirm": "Velvet-Chamber-9931",
        },
    )

    assert response.status_code == 200
    assert "current password is incorrect" in response.content.decode()


def test_portal_query_count_is_small(client, make_member, django_assert_max_num_queries):
    client.force_login(make_member())

    # session, user, membership, open payment, keys balance, featured treasure,
    # plus the layout badges: unread whispers and can-spin
    with django_assert_max_num_queries(8):
        client.get(reverse("core:portal"))
