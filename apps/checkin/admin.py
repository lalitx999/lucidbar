from django.contrib import admin

from .models import CheckIn


@admin.register(CheckIn)
class CheckInAdmin(admin.ModelAdmin):
    list_display = ("member", "night", "keys_awarded", "created_by", "created_at")
    list_select_related = ("member", "created_by")
    date_hierarchy = "night"
