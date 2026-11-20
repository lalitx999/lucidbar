from django import forms
from django.utils.translation import gettext_lazy as _

from apps.accounts.forms import LucidFormMixin


class SlipUploadForm(LucidFormMixin, forms.Form):
    slip = forms.FileField(
        label=_("Transfer slip"),
        widget=forms.ClearableFileInput(attrs={"accept": "image/jpeg,image/png,image/webp"}),
    )


class StaffApproveForm(LucidFormMixin, forms.Form):
    trans_ref = forms.CharField(
        label=_("Bank reference (optional)"),
        max_length=64,
        required=False,
        help_text=_("Record the transaction reference from the slip if you have it."),
    )


class StaffRejectForm(LucidFormMixin, forms.Form):
    reason = forms.CharField(
        label=_("Message to the member"),
        max_length=255,
        widget=forms.TextInput(attrs={"placeholder": _("For example: amount does not match")}),
    )
    allow_new_slip = forms.BooleanField(label=_("Let the member upload a new slip"), required=False, initial=True)
