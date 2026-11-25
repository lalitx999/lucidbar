from django import forms
from django.conf import settings
from django.core.validators import MaxValueValidator
from django.utils.translation import gettext_lazy as _

from apps.accounts.forms import LucidFormMixin
from apps.core.clock import business_night

from .models import TIME_SLOTS, Booking


class BookingForm(LucidFormMixin, forms.Form):
    night = forms.DateField(label=_("Night"), widget=forms.DateInput(attrs={"type": "date"}))
    time_slot = forms.ChoiceField(label=_("Time slot"), choices=TIME_SLOTS, initial="20:00")
    area = forms.ChoiceField(label=_("Chamber"), choices=Booking.Area.choices, initial=Booking.Area.SEATING)
    guests = forms.IntegerField(label=_("Guests"), min_value=1, initial=2)
    note = forms.CharField(
        label=_("Special requests"),
        max_length=300,
        required=False,
        widget=forms.Textarea(
            attrs={"rows": 2, "placeholder": _("Birthday celebration, bottle preference, and so on")}
        ),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        guests = self.fields["guests"]
        guests.validators.append(MaxValueValidator(settings.BOOKING_MAX_GUESTS))
        guests.widget.attrs["max"] = settings.BOOKING_MAX_GUESTS
        self.fields["night"].widget.attrs["min"] = business_night().isoformat()


class StaffDeclineForm(forms.Form):
    note = forms.CharField(max_length=300)


class StaffConfirmForm(forms.Form):
    note = forms.CharField(max_length=300, required=False)
