import threading
from collections import Counter
from datetime import UTC, datetime, timedelta
from unittest import mock

import pytest
from django.db import connection
from django.urls import reverse
from django.utils import timezone

from apps.memberships.models import Membership
from apps.reveal import wheel
from apps.reveal.models import ChosenDraw, WheelPrize, WheelSpin
from apps.reveal.selectors import reveal_selector
from apps.reveal.services import reveal_service
from apps.whispers.models import Whisper

NOTIFY = "apps.notifications.tasks.telegram"
pytestmark = pytest.mark.usefixtures("wheel_prizes")


# ---------------------------------------------------------------------------
# Epochs and wheel geometry
# ---------------------------------------------------------------------------
def test_epoch_number_uses_bangkok_iso_week():
    # Sunday 23:30 UTC is already Monday in Bangkok (UTC+7): next ISO week.
    moment = datetime(2026, 11, 22, 23, 30, tzinfo=UTC)
    assert reveal_service.epoch_number_for(moment) == 202648


@pytest.mark.django_db
def test_current_epoch_is_created_once():
    first = reveal_service.current_epoch()
    second = reveal_service.current_epoch()

    assert first.pk == second.pk
    assert (first.ends_at - first.starts_at) == timedelta(days=7)
    assert timezone.localtime(first.starts_at).weekday() == 0  # Monday


def test_landing_rotation_puts_segment_under_pointer():
    for index in range(12):
        rotation = wheel.landing_rotation(index, 12)
        # After rotating, the segment's centre angle must sit at 0 (12 o'clock).
        centre = (index + 0.5) * 30
        assert (centre + rotation) % 360 == pytest.approx(0)


def test_segments_are_full_circle_and_alternate():
    segs = wheel.segments([f"P{i}" for i in range(12)])

    assert len(segs) == 12
    assert segs[0].path.startswith("M0,0 L0.0,-100.0")
    assert [s.tone for s in segs[:3]] == ["gold", "dark", "gold"]


# ---------------------------------------------------------------------------
# The draw
# ---------------------------------------------------------------------------
@pytest.mark.django_db
def test_only_active_seal_holders_are_eligible(seal_member, make_member, staff_user):
    eligible = seal_member()
    make_member()  # no seal
    seal_member(status="suspended")
    staff_with_seal = staff_user
    from apps.memberships.services import membership_service

    membership_service.grant_signup_membership(staff_with_seal)
    expired = seal_member()
    Membership.objects.filter(member=expired).update(
        starts_at=timezone.now() - timedelta(days=31), ends_at=timezone.now() - timedelta(days=1)
    )

    assert reveal_service.eligible_member_ids() == [eligible.pk]


@pytest.mark.django_db(transaction=True)
def test_draw_picks_winner_and_whispers_them(seal_member, manager_user):
    members = [seal_member() for _ in range(3)]

    with mock.patch(NOTIFY) as tg:
        draw = reveal_service.run_draw(manager_user)

    assert draw.winner in members
    assert draw.eligible_count == 3
    assert Whisper.objects.filter(member=draw.winner, kind="reveal").exists()
    assert reveal_selector.can_spin(draw.winner)
    assert tg.send_message.called


@pytest.mark.django_db
def test_only_one_draw_per_week(seal_member, manager_user):
    seal_member()
    reveal_service.run_draw(manager_user)

    with pytest.raises(reveal_service.RevealError, match="already been drawn"):
        reveal_service.run_draw(manager_user)


@pytest.mark.django_db
def test_draw_with_nobody_eligible(manager_user):
    with pytest.raises(reveal_service.RevealError, match="No eligible"):
        reveal_service.run_draw(manager_user)


@pytest.mark.django_db(transaction=True)
def test_concurrent_draws_create_one(seal_member, manager_user):
    for _ in range(3):
        seal_member()
    reveal_service.current_epoch()  # create the row before the race
    barrier = threading.Barrier(5)
    outcomes = []

    def attempt():
        try:
            barrier.wait()
            with mock.patch(NOTIFY):
                reveal_service.run_draw(manager_user)
            outcomes.append("ok")
        except reveal_service.RevealError:
            outcomes.append("refused")
        finally:
            connection.close()

    threads = [threading.Thread(target=attempt) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert outcomes.count("ok") == 1
    assert ChosenDraw.objects.count() == 1


@pytest.mark.django_db
def test_draw_is_spread_across_members(seal_member, manager_user):
    """Sanity check of fairness: over many draws every member wins sometimes."""
    members = [seal_member() for _ in range(4)]
    wins = Counter()
    for _ in range(400):
        ChosenDraw.objects.all().delete()
        wins[reveal_service.run_draw(manager_user).winner_id] += 1

    assert set(wins) == {m.pk for m in members}
    assert min(wins.values()) > 50  # expected 100 each


# ---------------------------------------------------------------------------
# The spin
# ---------------------------------------------------------------------------
@pytest.fixture
def chosen(seal_member, manager_user):
    seal_member()
    return reveal_service.run_draw(manager_user).winner


@pytest.mark.django_db(transaction=True)
def test_chosen_spins_once_and_gets_claim(chosen):
    with mock.patch(NOTIFY):
        result = reveal_service.spin(chosen)

    assert result.status == WheelSpin.Status.READY
    assert len(result.claim_code) == 6
    prizes = reveal_selector.wheel_prizes()
    assert prizes[result.segment_index] == result.prize
    assert not reveal_selector.can_spin(chosen)
    with pytest.raises(reveal_service.RevealError, match="already spun"):
        reveal_service.spin(chosen)


@pytest.mark.django_db
def test_non_chosen_cannot_spin(chosen, seal_member):
    other = seal_member()

    with pytest.raises(reveal_service.RevealError, match="Only this week"):
        reveal_service.spin(other)


@pytest.mark.django_db
def test_zero_weight_prizes_never_win(chosen):
    WheelPrize.objects.exclude(label="Gym Membership").update(weight=0)

    result = reveal_service.spin(chosen)

    assert result.prize.label == "Gym Membership"


@pytest.mark.django_db
def test_weights_shape_the_odds():
    prizes = list(WheelPrize.objects.order_by("sort_order"))
    for p in prizes:
        p.weight = 0
    prizes[0].weight, prizes[1].weight = 9, 1
    counts = Counter(reveal_service._pick_prize(prizes) for _ in range(2000))

    assert set(counts) <= {0, 1}
    assert 0.8 < counts[0] / 2000 < 0.97  # expected 0.9


@pytest.mark.django_db
def test_hand_over_prize_once(chosen, staff_user):
    result = reveal_service.spin(chosen)

    reveal_service.hand_over_prize(result, staff_user)
    with pytest.raises(reveal_service.RevealError):
        reveal_service.hand_over_prize(result, staff_user)


# ---------------------------------------------------------------------------
# Views
# ---------------------------------------------------------------------------
@pytest.mark.django_db
def test_reveal_page_renders_wheel(client, seal_member):
    client.force_login(seal_member())

    html = client.get(reverse("reveal:reveal")).content.decode()

    assert html.count('class="wheel-slice') == 12
    assert "Awaiting the draw" in html
    assert "Spin the wheel" not in html


@pytest.mark.django_db
def test_chosen_sees_spin_button_and_tab_pulses(client, chosen):
    client.force_login(chosen)

    html = client.get(reverse("reveal:reveal")).content.decode()

    assert "Spin the wheel" in html
    assert "pulse text-gold" in html


@pytest.mark.django_db(transaction=True)
def test_spin_json_returns_rotation_for_animation(client, chosen):
    client.force_login(chosen)

    with mock.patch(NOTIFY):
        data = client.post(reverse("reveal:spin"), HTTP_ACCEPT="application/json").json()

    assert data["ok"] is True
    assert data["rotation"] == wheel.landing_rotation(data["segment"], 12)
    assert data["claim_code"] == WheelSpin.objects.get().claim_code


@pytest.mark.django_db
def test_spin_json_refuses_non_chosen(client, seal_member, chosen):
    client.force_login(seal_member())

    response = client.post(reverse("reveal:spin"), HTTP_ACCEPT="application/json")

    assert response.status_code == 400
    assert response.json()["ok"] is False


@pytest.mark.django_db(transaction=True)
def test_spin_without_javascript_redirects(client, chosen):
    client.force_login(chosen)

    with mock.patch(NOTIFY):
        response = client.post(reverse("reveal:spin"))

    assert response["Location"] == reverse("reveal:reveal")
    page = client.get(reverse("reveal:reveal")).content.decode()
    assert WheelSpin.objects.get().claim_code in page
