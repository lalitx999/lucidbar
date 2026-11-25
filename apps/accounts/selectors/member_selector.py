from ..models import Member


def get_member_by_email(email: str) -> Member | None:
    if not email:
        return None
    return Member.objects.filter(email__iexact=email.strip()).first()


def get_member_by_id(member_id) -> Member | None:
    if not member_id:
        return None
    return Member.objects.filter(pk=member_id).first()


def email_exists(email: str) -> bool:
    return Member.objects.filter(email__iexact=email.strip()).exists()


def phone_exists(country_code: str, phone: str, exclude_pk=None) -> bool:
    qs = Member.objects.filter(country_code=country_code, phone=phone)
    if exclude_pk is not None:
        qs = qs.exclude(pk=exclude_pk)
    return qs.exists()


def search_members(query: str = "", status: str = "", limit: int = 50):
    """Member list for managers. Staff accounts are excluded."""
    from django.db.models import Q

    qs = Member.objects.filter(is_staff=False)
    if status:
        qs = qs.filter(status=status)
    query = query.strip()
    if query:
        qs = qs.filter(
            Q(email__icontains=query)
            | Q(full_name__icontains=query)
            | Q(handle__icontains=query.lstrip("@"))
            | Q(phone__icontains=query)
        )
    return (
        qs.select_related("keys_account")
        .only(
            "pk",
            "email",
            "full_name",
            "handle",
            "country_code",
            "phone",
            "status",
            "date_joined",
            "keys_account__balance",
        )
        .order_by("-date_joined")[:limit]
    )


def member_for_staff_or_404(member_id: int) -> Member:
    from django.shortcuts import get_object_or_404

    return get_object_or_404(Member.objects.filter(is_staff=False), pk=member_id)
