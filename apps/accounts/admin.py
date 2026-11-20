from django.contrib import admin

from .models import EmailOTP, Member


@admin.register(Member)
class MemberAdmin(admin.ModelAdmin):
    """Superuser maintenance view. Staff use the custom dashboard instead."""

    list_display = ("email", "full_name", "handle", "status", "is_staff", "date_joined")
    list_filter = ("status", "is_staff")
    search_fields = ("email", "full_name", "handle", "phone")
    readonly_fields = ("password", "last_login", "date_joined", "updated_at", "email_verified_at")
    ordering = ("-date_joined",)
    filter_horizontal = ("groups", "user_permissions")


@admin.register(EmailOTP)
class EmailOTPAdmin(admin.ModelAdmin):
    list_display = ("member", "purpose", "created_at", "expires_at", "attempts", "consumed_at")
    list_filter = ("purpose",)
    list_select_related = ("member",)
    readonly_fields = [f.name for f in EmailOTP._meta.fields]

    def has_add_permission(self, request):
        return False
