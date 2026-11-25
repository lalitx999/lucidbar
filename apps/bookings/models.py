import datetime as dt

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils.translation import gettext_lazy as _

# Same slots as the original booking form. 00:00 and 01:00 belong to the
# night they follow (see apps.core.clock).
TIME_SLOTS = [
    ("19:00", _("19:00 Early lounge")),
    ("20:00", _("20:00 Recommended")),
    ("21:00", "21:00"),
    ("22:00", _("22:00 Peak hours")),
    ("23:00", "23:00"),
    ("00:00", _("00:00 Midnight show")),
    ("01:00", _("01:00 Late night")),
]


class Booking(models.Model):
    """A VIP Chamber request. Staff confirm or decline it from the dashboard."""

    class Status(models.TextChoices):
        REQUESTED = "requested", _("Requested")
        CONFIRMED = "confirmed", _("Confirmed")
        DECLINED = "declined", _("Declined")
        CANCELLED = "cancelled", _("Cancelled")

    class Area(models.TextChoices):
        CLUB = "club", _("Club access")
        SEATING = "seating", _("Exclusive seating")
        SALON = "salon", _("Private salon")

    OPEN_STATUSES = (Status.REQUESTED, Status.CONFIRMED)

    reference = models.CharField(max_length=8, unique=True)
    member = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="bookings")
    night = models.DateField(help_text="The club night of the visit")
    time_slot = models.CharField(max_length=5, choices=TIME_SLOTS)
    starts_at = models.DateTimeField()
    area = models.CharField(max_length=10, choices=Area.choices, default=Area.SEATING)
    guests = models.PositiveSmallIntegerField()
    note = models.CharField(max_length=300, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.REQUESTED)
    staff_note = models.CharField(max_length=300, blank=True)
    handled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    handled_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["starts_at", "id"]
        indexes = [models.Index(fields=["status", "starts_at"], name="booking_status_start_idx")]
        constraints = [
            models.CheckConstraint(condition=Q(guests__gte=1) & Q(guests__lte=50), name="booking_guests_range"),
            models.UniqueConstraint(
                fields=["member", "night"],
                condition=Q(status__in=["requested", "confirmed"]),
                name="booking_one_open_per_night",
            ),
        ]

    def __str__(self):
        return f"{self.reference} {self.night} {self.time_slot}"

    @property
    def slot_time(self) -> dt.time:
        return dt.time.fromisoformat(self.time_slot)

    @property
    def is_open(self) -> bool:
        return self.status in self.OPEN_STATUSES
