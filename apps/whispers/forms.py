from django import forms
from django.utils.translation import gettext_lazy as _

from apps.accounts.forms import LucidFormMixin

from .models import Broadcast


class BroadcastForm(LucidFormMixin, forms.Form):
    title = forms.CharField(label=_("Title"), max_length=120)
    body = forms.CharField(label=_("Message"), max_length=2000, widget=forms.Textarea(attrs={"rows": 5}))
    audience = forms.ChoiceField(label=_("Send to"), choices=Broadcast.Audience.choices)
