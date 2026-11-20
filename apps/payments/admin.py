from django.contrib import admin

from .models import PaymentIntent, PaymentSlip


class PaymentSlipInline(admin.TabularInline):
    model = PaymentSlip
    extra = 0
    can_delete = False
    fields = ("created_at", "status", "trans_ref", "slip_amount_satang", "provider_code", "note")
    readonly_fields = fields


@admin.register(PaymentIntent)
class PaymentIntentAdmin(admin.ModelAdmin):
    """Read-only maintenance view. Decisions are made in the staff dashboard."""

    list_display = ("reference", "member", "tier", "amount_satang", "status", "created_at")
    list_filter = ("status", "tier")
    list_select_related = ("member", "tier")
    search_fields = ("reference", "member__email")
    inlines = [PaymentSlipInline]
    readonly_fields = [f.name for f in PaymentIntent._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
