from django.contrib import admin

from .models import Broadcast, Whisper


@admin.register(Broadcast)
class BroadcastAdmin(admin.ModelAdmin):
    list_display = ("title", "audience", "recipients", "sent_by", "created_at")
    list_select_related = ("sent_by",)
    readonly_fields = ("recipients", "sent_by", "created_at")


@admin.register(Whisper)
class WhisperAdmin(admin.ModelAdmin):
    list_display = ("member", "kind", "title", "is_read", "created_at")
    list_filter = ("kind", "is_read")
    list_select_related = ("member",)
    search_fields = ("member__email", "title")
