from django.contrib import admin

from .models import ChosenDraw, Epoch, WheelPrize, WheelSpin


@admin.register(WheelPrize)
class WheelPrizeAdmin(admin.ModelAdmin):
    list_display = ("label", "value_text", "weight", "sort_order", "is_active")
    list_editable = ("weight", "sort_order", "is_active")


@admin.register(Epoch)
class EpochAdmin(admin.ModelAdmin):
    list_display = ("number", "starts_at", "ends_at")


@admin.register(ChosenDraw)
class ChosenDrawAdmin(admin.ModelAdmin):
    list_display = ("epoch", "winner", "eligible_count", "drawn_by", "created_at")
    list_select_related = ("epoch", "winner", "drawn_by")
    readonly_fields = [f.name for f in ChosenDraw._meta.fields]

    def has_add_permission(self, request):
        return False


@admin.register(WheelSpin)
class WheelSpinAdmin(admin.ModelAdmin):
    list_display = ("claim_code", "member", "prize", "status", "created_at")
    list_select_related = ("member", "prize")
    readonly_fields = [f.name for f in WheelSpin._meta.fields]

    def has_add_permission(self, request):
        return False
