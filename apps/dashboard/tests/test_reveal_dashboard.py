from unittest import mock

import pytest
from django.urls import reverse

from apps.reveal.models import ChosenDraw, WheelSpin
from apps.reveal.services import reveal_service

pytestmark = [pytest.mark.django_db, pytest.mark.usefixtures("wheel_prizes")]


def test_staff_sees_page_but_cannot_draw(client, staff_user, seal_member):
    seal_member()
    client.force_login(staff_user)

    html = client.get(reverse("dashboard:reveal")).content.decode()
    assert "A manager runs the weekly draw" in html
    assert client.post(reverse("dashboard:reveal_draw")).status_code == 403
    assert not ChosenDraw.objects.exists()


def test_manager_draws(client, manager_user, seal_member):
    member = seal_member(full_name="Lucky Member")
    client.force_login(manager_user)

    with mock.patch("apps.notifications.tasks.telegram"):
        response = client.post(reverse("dashboard:reveal_draw"), follow=True)

    assert "Lucky Member" in response.content.decode()
    assert ChosenDraw.objects.get().winner == member


def test_staff_hands_over_prize(client, staff_user, manager_user, seal_member):
    member = seal_member()
    reveal_service.run_draw(manager_user)
    result = reveal_service.spin(member)
    client.force_login(staff_user)

    page = client.get(reverse("dashboard:reveal"), {"q": result.claim_code}).content.decode()
    assert result.claim_code in page
    client.post(reverse("dashboard:prize_hand_over", args=[result.pk]))

    result.refresh_from_db()
    assert result.status == WheelSpin.Status.HANDED_OVER
    assert result.handled_by == staff_user
