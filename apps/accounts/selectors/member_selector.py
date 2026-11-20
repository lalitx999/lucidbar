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
