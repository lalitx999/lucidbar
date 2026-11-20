from django.contrib import admin

from .models import KeysAccount, KeysEntry


@admin.register(KeysAccount)
class KeysAccountAdmin(admin.ModelAdmin):
    """Read-only: balances change only through the ledger service."""

    list_display = ("member", "balance", "updated_at")
    list_select_related = ("member",)
    search_fields = ("member__email",)
    readonly_fields = ("member", "balance", "updated_at")

    def has_add_permission(self, request):
        return False


@admin.register(KeysEntry)
class KeysEntryAdmin(admin.ModelAdmin):
    list_display = ("account", "delta", "balance_after", "reason", "reference", "created_at")
    list_filter = ("reason",)
    list_select_related = ("account__member",)
    search_fields = ("account__member__email", "reference")
    readonly_fields = [f.name for f in KeysEntry._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
