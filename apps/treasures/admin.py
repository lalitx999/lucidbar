from django.contrib import admin

from .models import Redemption, Treasure


@admin.register(Treasure)
class TreasureAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "keys_cost", "stock", "is_featured", "is_active", "sort_order")
    list_filter = ("category", "is_active", "is_featured")
    list_editable = ("keys_cost", "stock", "is_featured", "is_active", "sort_order")
    search_fields = ("name",)


@admin.register(Redemption)
class RedemptionAdmin(admin.ModelAdmin):
    list_display = ("claim_code", "member", "treasure", "keys_spent", "status", "created_at")
    list_filter = ("status",)
    list_select_related = ("member", "treasure")
    search_fields = ("claim_code", "member__email")
    readonly_fields = [f.name for f in Redemption._meta.fields]

    def has_add_permission(self, request):
        return False
