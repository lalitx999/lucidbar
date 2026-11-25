from django.contrib import admin

from .models import Booking


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ("reference", "member", "night", "time_slot", "area", "guests", "status")
    list_filter = ("status", "area")
    list_select_related = ("member",)
    search_fields = ("reference", "member__email")
