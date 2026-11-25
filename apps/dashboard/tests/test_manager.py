import uuid

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from apps.accounts.models import Member
from apps.audit.models import AuditEntry
from apps.keys.models import KeysAccount, Spending
from apps.keys.services import ledger_service
from apps.memberships.models import Membership, SealTier
from apps.reveal.models import WheelPrize
from apps.treasures.models import Treasure
from apps.whispers.models import Whisper
from tests.fixtures import make_image_bytes

pytestmark = [pytest.mark.django_db, pytest.mark.usefixtures("seal_tiers", "wheel_prizes")]


def _balance(member):
    account = KeysAccount.objects.filter(member=member).first()
    return account.balance if account else 0


# ---------------------------------------------------------------------------
# Roles
# ---------------------------------------------------------------------------
MANAGER_PAGES = [
    ("dashboard:overview", []),
    ("dashboard:members", []),
    ("dashboard:catalog", []),
    ("dashboard:treasure_new", []),
    ("dashboard:tiers", []),
    ("dashboard:prizes", []),
    ("dashboard:prize_new", []),
    ("dashboard:audit", []),
    ("dashboard:payments", []),
]


@pytest.mark.parametrize(("name", "args"), MANAGER_PAGES)
def test_manager_pages_refuse_plain_staff(client, staff_user, name, args):
    client.force_login(staff_user)

    assert client.get(reverse(name, args=args)).status_code == 403


@pytest.mark.parametrize(("name", "args"), MANAGER_PAGES)
def test_manager_pages_render(client, manager_user, name, args):
    client.force_login(manager_user)

    assert client.get(reverse(name, args=args)).status_code == 200


def test_edit_pages_render(client, manager_user, make_member):
    member = make_member()
    treasure = Treasure.objects.create(name="Cognac", keys_cost=10)
    client.force_login(manager_user)

    for url in [
        reverse("dashboard:member_detail", args=[member.pk]),
        reverse("dashboard:tier_edit", args=[SealTier.objects.get(code="gold").pk]),
        reverse("dashboard:prize_edit", args=[WheelPrize.objects.first().pk]),
        reverse("dashboard:treasure_edit", args=[treasure.pk]),
    ]:
        assert client.get(url).status_code == 200, url


def test_home_depends_on_role(client, staff_user, manager_user):
    client.force_login(staff_user)
    assert client.get(reverse("dashboard:home"))["Location"] == reverse("dashboard:door")
    html = client.get(reverse("dashboard:door")).content.decode()
    assert reverse("dashboard:members") not in html

    client.force_login(manager_user)
    assert client.get(reverse("dashboard:home"))["Location"] == reverse("dashboard:overview")


def test_staff_detail_page_is_not_reachable_for_staff_accounts(client, manager_user, staff_user):
    client.force_login(manager_user)

    assert client.get(reverse("dashboard:member_detail", args=[staff_user.pk])).status_code == 404


# ---------------------------------------------------------------------------
# Members
# ---------------------------------------------------------------------------
def test_member_search(client, manager_user, make_member):
    make_member(full_name="Alice Velvet")
    make_member(full_name="Bob Onyx")
    client.force_login(manager_user)

    html = client.get(reverse("dashboard:members"), {"q": "velvet"}).content.decode()

    assert "Alice Velvet" in html and "Bob Onyx" not in html


def test_members_list_query_count(client, manager_user, make_member, django_assert_max_num_queries):
    for _ in range(10):
        make_member()
    client.force_login(manager_user)

    with django_assert_max_num_queries(5):
        client.get(reverse("dashboard:members"))


def test_suspend_needs_reason_and_ends_sessions(client, manager_user, make_member):
    member = make_member()
    member_client = client.__class__()
    member_client.force_login(member)
    client.force_login(manager_user)
    url = reverse("dashboard:member_suspend", args=[member.pk])

    assert client.post(url, {"reason": ""}).status_code == 200  # form shown again
    member.refresh_from_db()
    assert member.status == Member.Status.ACTIVE

    client.post(url, {"reason": "Chargeback"})

    member.refresh_from_db()
    assert member.status == Member.Status.SUSPENDED
    assert member_client.get(reverse("core:portal")).status_code == 302  # signed out
    entry = AuditEntry.objects.get(action="member.suspend")
    assert entry.details["reason"] == "Chargeback" and entry.actor == manager_user


def test_reactivate_tells_member(client, manager_user, make_member):
    member = make_member(status=Member.Status.SUSPENDED)
    client.force_login(manager_user)

    client.post(reverse("dashboard:member_reactivate", args=[member.pk]))

    member.refresh_from_db()
    assert member.status == Member.Status.ACTIVE
    assert Whisper.objects.filter(member=member).exists()
    assert AuditEntry.objects.filter(action="member.reactivate").exists()


def test_adjust_keys_up_and_down(client, manager_user, make_member):
    member = make_member()
    client.force_login(manager_user)
    url = reverse("dashboard:member_adjust_keys", args=[member.pk])

    client.post(url, {"delta": 20, "note": "Birthday gift", "tell_member": "on"})
    client.post(url, {"delta": -5, "note": "Correction"})
    response = client.post(url, {"delta": -100, "note": "Too much"}, follow=True)

    assert _balance(member) == 15
    assert "Not enough keys" in response.content.decode()
    assert AuditEntry.objects.filter(action="keys.adjust").count() == 2
    assert Whisper.objects.filter(member=member).count() == 1  # only the first asked to tell


def test_grant_complimentary_seal(client, manager_user, make_member):
    member = make_member()
    gold = SealTier.objects.get(code="gold")
    client.force_login(manager_user)

    client.post(reverse("dashboard:member_grant_seal", args=[member.pk]), {"tier": gold.pk, "days": 7})

    membership = Membership.objects.get(member=member, source=Membership.Source.STAFF)
    assert (membership.ends_at - membership.starts_at).days == 7
    assert _balance(member) == 0  # keys only when asked
    assert AuditEntry.objects.filter(action="membership.grant").exists()


def test_member_detail_query_count(client, manager_user, make_member, django_assert_max_num_queries):
    member = make_member()
    ledger_service.post_entry(member, 5, "admin_adjust", note="x")
    client.force_login(manager_user)

    with django_assert_max_num_queries(16):
        client.get(reverse("dashboard:member_detail", args=[member.pk]))


# ---------------------------------------------------------------------------
# Spending
# ---------------------------------------------------------------------------
def test_staff_records_spending_once_per_form(client, staff_user, make_member, settings):
    settings.SPENDING_THB_PER_KEY = 100
    member = make_member()
    client.force_login(staff_user)
    payload = {"amount": "1250.50", "note": "Table 4", "nonce": str(uuid.uuid4()), "back": "checkin:7"}
    url = reverse("dashboard:member_spending", args=[member.pk])

    first = client.post(url, payload)
    client.post(url, payload)  # double submit

    assert first["Location"] == reverse("dashboard:door") + "?last=7"
    spending = Spending.objects.get()
    assert spending.amount_satang == 125050 and spending.keys_awarded == 12
    assert _balance(member) == 12


def test_spending_refused_for_suspended_member(client, staff_user, make_member):
    member = make_member(status=Member.Status.SUSPENDED)
    client.force_login(staff_user)

    client.post(reverse("dashboard:member_spending", args=[member.pk]), {"amount": "500", "nonce": str(uuid.uuid4())})

    assert not Spending.objects.exists()


# ---------------------------------------------------------------------------
# Seal tiers
# ---------------------------------------------------------------------------
def _tier_payload(tier, **changes):
    data = {
        "name": tier.name,
        "tagline": tier.tagline,
        "price_thb": str(tier.price_satang / 100),
        "period_days": tier.period_days,
        "initial_keys": tier.initial_keys,
        "benefits": tier.benefits,
        "is_active": "on" if tier.is_active else "",
    }
    data.update(changes)
    return data


def test_change_gold_price(client, manager_user):
    gold = SealTier.objects.get(code="gold")
    client.force_login(manager_user)

    client.post(reverse("dashboard:tier_edit", args=[gold.pk]), _tier_payload(gold, price_thb="549.00"))

    gold.refresh_from_db()
    assert gold.price_satang == 54900
    assert "price_satang" in AuditEntry.objects.get(action="tier.update").details


def test_free_tier_cannot_become_paid_or_hidden(client, manager_user):
    bronze = SealTier.objects.get(code="bronze")
    client.force_login(manager_user)
    url = reverse("dashboard:tier_edit", args=[bronze.pk])

    first = client.post(url, _tier_payload(bronze, price_thb="10", period_days=30))
    second = client.post(url, _tier_payload(bronze, is_active=""))

    bronze.refresh_from_db()
    assert bronze.price_satang == 0 and bronze.is_active
    assert "cannot become paid" in first.content.decode()
    assert "Keep this one active" in second.content.decode()


# ---------------------------------------------------------------------------
# Wheel prizes
# ---------------------------------------------------------------------------
def _prize_payload(prize=None, **changes):
    data = {"label": "", "value_text": "", "description": "", "weight": 1, "sort_order": 99, "is_active": "on"}
    if prize:
        data.update(
            label=prize.label,
            value_text=prize.value_text,
            description=prize.description,
            weight=prize.weight,
            sort_order=prize.sort_order,
            is_active="on" if prize.is_active else "",
        )
    data.update(changes)
    return data


def test_add_prize(client, manager_user):
    client.force_login(manager_user)

    client.post(reverse("dashboard:prize_new"), _prize_payload(label="Private Show", weight=2))

    assert WheelPrize.objects.filter(label="Private Show", weight=2).exists()
    assert AuditEntry.objects.filter(action="prize.create").exists()


def test_wheel_keeps_at_least_two_prizes(client, manager_user):
    prizes = list(WheelPrize.objects.order_by("sort_order"))
    WheelPrize.objects.exclude(pk__in=[prizes[0].pk, prizes[1].pk]).update(is_active=False)
    client.force_login(manager_user)

    response = client.post(
        reverse("dashboard:prize_edit", args=[prizes[0].pk]), _prize_payload(prizes[0], is_active="")
    )

    assert "between 2 and 24" in response.content.decode()
    assert WheelPrize.objects.get(pk=prizes[0].pk).is_active  # rolled back
    assert not AuditEntry.objects.exists()


def test_wheel_needs_a_winnable_prize(client, manager_user):
    prizes = list(WheelPrize.objects.order_by("sort_order"))
    WheelPrize.objects.exclude(pk=prizes[0].pk).update(weight=0)
    client.force_login(manager_user)

    response = client.post(reverse("dashboard:prize_edit", args=[prizes[0].pk]), _prize_payload(prizes[0], weight=0))

    assert "weight above zero" in response.content.decode()
    assert WheelPrize.objects.get(pk=prizes[0].pk).weight == 1


def test_resting_wheel_follows_prize_after_reorder(client, manager_user, seal_member):
    from apps.reveal import wheel
    from apps.reveal.services import reveal_service

    member = seal_member()
    reveal_service.run_draw(manager_user)
    result = reveal_service.spin(member)
    # Move the won prize to the front of the wheel.
    result.prize.sort_order = 0
    result.prize.save()
    WheelPrize.objects.exclude(pk=result.prize.pk).update(sort_order=50)
    client.force_login(member)

    response = client.get(reverse("reveal:reveal"))

    assert response.context["resting_rotation"] == wheel.landing_rotation(0, 12, 0)


# ---------------------------------------------------------------------------
# Treasures
# ---------------------------------------------------------------------------
def _treasure_payload(**changes):
    data = {
        "name": "Dom Perignon",
        "category": "spirits",
        "description": "Vintage",
        "keys_cost": 120,
        "stock": 3,
        "sort_order": 1,
        "is_featured": "",
        "is_active": "on",
    }
    data.update(changes)
    return data


def test_create_treasure_with_picture(client, manager_user):
    client.force_login(manager_user)
    picture = SimpleUploadedFile("p.png", make_image_bytes(fmt="PNG", size=(2400, 1600)), content_type="image/png")

    client.post(reverse("dashboard:treasure_new"), {**_treasure_payload(), "new_image": picture})

    treasure = Treasure.objects.get(name="Dom Perignon")
    assert treasure.image.name.endswith(".jpg")
    from PIL import Image

    with treasure.image.open("rb") as fh, Image.open(fh) as img:
        assert img.format == "JPEG" and max(img.size) == 1200
    assert AuditEntry.objects.filter(action="treasure.create").exists()


def test_bad_picture_is_refused(client, manager_user):
    client.force_login(manager_user)
    fake = SimpleUploadedFile("p.png", b"not an image", content_type="image/png")

    response = client.post(reverse("dashboard:treasure_new"), {**_treasure_payload(), "new_image": fake})

    assert response.status_code == 200
    assert not Treasure.objects.exists()


def test_edit_treasure_stock_and_hide(client, manager_user):
    treasure = Treasure.objects.create(name="Cigar", keys_cost=30, stock=1)
    client.force_login(manager_user)

    client.post(
        reverse("dashboard:treasure_edit", args=[treasure.pk]),
        _treasure_payload(name="Cigar", keys_cost=30, stock="", is_active=""),
    )

    treasure.refresh_from_db()
    assert treasure.stock is None and not treasure.is_active
    entry = AuditEntry.objects.get(action="treasure.update")
    assert "stock" in entry.details and "is_active" in entry.details


# ---------------------------------------------------------------------------
# Overview and audit log
# ---------------------------------------------------------------------------
def test_overview_counts_spending_and_members(client, manager_user, staff_user, make_member):
    from apps.keys.services import spending_service

    member = make_member()
    spending_service.record(member, 300000, staff_user, nonce=uuid.uuid4())
    client.force_login(manager_user)

    report = client.get(reverse("dashboard:overview")).context["report"]

    assert report["spending_thb"] == 3000
    assert report["members"]["active"] >= 1
    assert report["keys_issued"] == 30


def test_audit_log_filters(client, manager_user, make_member):
    member = make_member()
    from apps.keys.services import adjust_service

    adjust_service.adjust(member, 3, "Gift", manager_user)
    client.force_login(manager_user)

    html = client.get(reverse("dashboard:audit"), {"type": "keys"}).content.decode()
    assert "keys.adjust" in html
    html = client.get(reverse("dashboard:audit"), {"type": "member"}).content.decode()
    assert "keys.adjust" not in html
