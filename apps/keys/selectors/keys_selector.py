from ..models import KeysAccount, KeysEntry


def balance_of(member) -> int:
    value = KeysAccount.objects.filter(member=member).values_list("balance", flat=True).first()
    return value or 0


def history(member):
    """Ledger lines for the Keys page, newest first. Paginate in the view."""
    return KeysEntry.objects.filter(account__member=member).only(
        "delta", "balance_after", "reason", "note", "created_at"
    )
