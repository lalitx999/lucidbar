"""Forms for the staff dashboard. They only validate; services do the writing."""

import uuid
from decimal import Decimal

from django import forms
from django.conf import settings
from django.utils.translation import gettext_lazy as _

from apps.accounts.forms import LucidFormMixin
from apps.memberships.models import SealTier
from apps.reveal.models import WheelPrize
from apps.treasures.models import Treasure


class SuspendForm(LucidFormMixin, forms.Form):
    reason = forms.CharField(label=_("Reason"), max_length=200)


class KeysAdjustForm(LucidFormMixin, forms.Form):
    delta = forms.IntegerField(
        label=_("Keys"), min_value=-100_000, max_value=100_000, help_text=_("Negative removes keys.")
    )
    note = forms.CharField(label=_("Reason"), max_length=200)
    tell_member = forms.BooleanField(label=_("Tell the member in Whispers"), required=False, initial=True)

    def clean_delta(self):
        delta = self.cleaned_data["delta"]
        if delta == 0:
            raise forms.ValidationError(_("Enter a number other than zero."))
        return delta


class GrantSealForm(LucidFormMixin, forms.Form):
    tier = forms.ModelChoiceField(label=_("Seal"), queryset=SealTier.objects.none(), empty_label=None)
    days = forms.IntegerField(label=_("Days"), min_value=1, max_value=3650, initial=30)
    credit_keys = forms.BooleanField(label=_("Also credit the seal's keys"), required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["tier"].queryset = SealTier.objects.filter(is_active=True, price_satang__gt=0).order_by(
            "sort_order"
        )


class SpendingForm(LucidFormMixin, forms.Form):
    amount = forms.DecimalField(label=_("Bill (THB)"), min_value=Decimal("1"), max_digits=9, decimal_places=2)
    note = forms.CharField(label=_("Note"), max_length=120, required=False)
    nonce = forms.UUIDField(widget=forms.HiddenInput)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["nonce"].initial = uuid.uuid4()
        self.fields["amount"].max_value = settings.SPENDING_MAX_THB
        self.fields["amount"].help_text = _("1 key for every %(n)d THB.") % {"n": settings.SPENDING_THB_PER_KEY}

    @property
    def amount_satang(self) -> int:
        return int(self.cleaned_data["amount"] * 100)


class TierForm(LucidFormMixin, forms.ModelForm):
    price_thb = forms.DecimalField(label=_("Price (THB)"), min_value=Decimal("0"), max_digits=9, decimal_places=2)

    class Meta:
        model = SealTier
        fields = ["name", "tagline", "period_days", "initial_keys", "benefits", "is_active"]
        widgets = {"benefits": forms.Textarea(attrs={"rows": 4})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["price_thb"].initial = self.instance.price_satang / 100

    def service_values(self) -> dict:
        values = {f: self.cleaned_data[f] for f in self.Meta.fields}
        values["price_satang"] = int(self.cleaned_data["price_thb"] * 100)
        return values


class PrizeForm(LucidFormMixin, forms.ModelForm):
    class Meta:
        model = WheelPrize
        fields = ["label", "value_text", "description", "weight", "sort_order", "is_active"]

    def service_values(self) -> dict:
        return {f: self.cleaned_data[f] for f in self.Meta.fields}


class TreasureForm(LucidFormMixin, forms.ModelForm):
    new_image = forms.ImageField(label=_("Picture"), required=False, help_text=_("JPG, PNG or WEBP, under 8 MB."))
    remove_image = forms.BooleanField(label=_("Remove the current picture"), required=False)

    class Meta:
        model = Treasure
        fields = ["name", "category", "description", "keys_cost", "stock", "sort_order", "is_featured", "is_active"]
        widgets = {"description": forms.Textarea(attrs={"rows": 3})}

    def service_values(self) -> dict:
        return {f: self.cleaned_data[f] for f in self.Meta.fields}
