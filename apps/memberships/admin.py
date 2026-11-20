from django.contrib import admin

from .models import Membership, SealTier


@admin.register(SealTier)
class SealTierAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "price_satang", "period_days", "initial_keys", "sort_order", "is_active")
    ordering = ("sort_order",)


@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin):
    list_display = ("member", "tier", "source", "starts_at", "ends_at")
    list_filter = ("tier", "source")
    list_select_related = ("member", "tier")
    search_fields = ("member__email",)
    raw_id_fields = ("member", "payment_intent")
