"""
The weekly Reveal: draw The Chosen, then let the winner spin the wheel once.

Randomness comes from secrets.SystemRandom (the OS CSPRNG), never `random`.
The server decides every outcome; the browser only animates the result.
"""

import secrets
from datetime import datetime, time, timedelta

from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone
from django.utils.translation import gettext as _

from apps.audit.services import audit_service
from apps.whispers.models import Whisper
from apps.whispers.services import whisper_service

from ..models import ChosenDraw, Epoch, WheelPrize, WheelSpin

_rng = secrets.SystemRandom()
CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


class RevealError(Exception):
    """User-safe message."""


# ---------------------------------------------------------------------------
# Epochs
# ---------------------------------------------------------------------------
def epoch_number_for(moment: datetime) -> int:
    year, week, _weekday = timezone.localtime(moment).isocalendar()
    return year * 100 + week


def current_epoch(now: datetime | None = None) -> Epoch:
    """The epoch for this ISO week (Bangkok time), created on first use."""
    now = now or timezone.now()
    local = timezone.localtime(now)
    monday = local.date() - timedelta(days=local.weekday())
    starts = timezone.make_aware(datetime.combine(monday, time.min))
    epoch, _created = Epoch.objects.get_or_create(
        number=epoch_number_for(now),
        defaults={"starts_at": starts, "ends_at": starts + timedelta(days=7)},
    )
    return epoch


# ---------------------------------------------------------------------------
# The draw
# ---------------------------------------------------------------------------
def eligible_member_ids(at: datetime | None = None) -> list[int]:
    """Active, verified, non-staff members who hold any active seal."""
    from apps.accounts.models import Member

    at = at or timezone.now()
    return list(
        Member.objects.filter(status=Member.Status.ACTIVE, is_staff=False)
        .filter(memberships__starts_at__lte=at)
        .filter(Q(memberships__ends_at__isnull=True) | Q(memberships__ends_at__gt=at))
        .values_list("pk", flat=True)
        .distinct()
        .order_by("pk")
    )


def run_draw(staff) -> ChosenDraw:
    """Pick this week's Chosen. Only one draw per epoch, enforced by the database."""
    from apps.accounts.models import Member
    from apps.notifications.tasks import notify_reveal

    epoch = current_epoch()
    with transaction.atomic():
        # Lock the epoch row so two managers pressing the button cannot both draw.
        epoch = Epoch.objects.select_for_update().get(pk=epoch.pk)
        if ChosenDraw.objects.filter(epoch=epoch).exists():
            raise RevealError(_("This week's Chosen has already been drawn."))
        candidates = eligible_member_ids()
        if not candidates:
            raise RevealError(_("No eligible members to draw from."))
        winner = Member.objects.get(pk=_rng.choice(candidates))
        draw = ChosenDraw.objects.create(epoch=epoch, winner=winner, eligible_count=len(candidates), drawn_by=staff)
        if staff is not None:
            audit_service.record(staff, "reveal.draw", winner, epoch=epoch.label, eligible=len(candidates))
        whisper_service.send(
            winner,
            _("You are The Chosen"),
            _("You were drawn for %(epoch)s. Open the Reveal tab to spin the wheel.") % {"epoch": epoch.label},
            kind=Whisper.Kind.REVEAL,
        )
        transaction.on_commit(lambda: notify_reveal.delay(draw.pk, "drawn"))
    return draw


# ---------------------------------------------------------------------------
# The spin
# ---------------------------------------------------------------------------
def _pick_prize(prizes: list[WheelPrize]) -> int:
    """Index of the winning segment, weighted. Zero-weight segments never win."""
    weights = [p.weight for p in prizes]
    if sum(weights) <= 0:
        raise RevealError(_("The wheel is not ready. Please contact the club."))
    return _rng.choices(range(len(prizes)), weights=weights, k=1)[0]


def spin(member) -> WheelSpin:
    """The Chosen spins once for the current epoch."""
    from apps.notifications.tasks import notify_reveal

    epoch = current_epoch()
    with transaction.atomic():
        draw = ChosenDraw.objects.select_for_update().filter(epoch=epoch, winner=member).first()
        if draw is None:
            raise RevealError(_("Only this week's Chosen can spin the wheel."))
        if WheelSpin.objects.filter(draw=draw).exists():
            raise RevealError(_("You have already spun the wheel this week."))

        prizes = list(WheelPrize.objects.filter(is_active=True).order_by("sort_order", "pk"))
        index = _pick_prize(prizes)
        prize = prizes[index]
        for _attempt in range(5):
            try:
                with transaction.atomic():
                    result = WheelSpin.objects.create(
                        draw=draw,
                        member=member,
                        prize=prize,
                        segment_index=index,
                        claim_code="".join(secrets.choice(CODE_ALPHABET) for _ in range(6)),
                    )
                break
            except IntegrityError:
                if WheelSpin.objects.filter(draw=draw).exists():
                    raise RevealError(_("You have already spun the wheel this week.")) from None
        else:
            raise RuntimeError("Could not allocate a unique claim code")

        whisper_service.send(
            member,
            _("You won: %(prize)s") % {"prize": prize.label},
            _("%(desc)s. Show claim code %(code)s to our staff to collect it.")
            % {"desc": prize.description or prize.label, "code": result.claim_code},
            kind=Whisper.Kind.REVEAL,
        )
        transaction.on_commit(lambda: notify_reveal.delay(draw.pk, "spun"))
    return result


def hand_over_prize(wheel_spin: WheelSpin, staff) -> WheelSpin:
    with transaction.atomic():
        wheel_spin = WheelSpin.objects.select_for_update().get(pk=wheel_spin.pk)
        if wheel_spin.status != WheelSpin.Status.READY:
            raise RevealError(_("This prize has already been collected."))
        wheel_spin.status = WheelSpin.Status.HANDED_OVER
        wheel_spin.handled_by = staff
        wheel_spin.handled_at = timezone.now()
        wheel_spin.save(update_fields=["status", "handled_by", "handled_at"])
    return wheel_spin
