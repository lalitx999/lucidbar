"""Member profile changes."""

from django.contrib.auth import update_session_auth_hash

from ..models import Member

EDITABLE_FIELDS = ("full_name", "country_code", "phone", "nationality")


def update_profile(member: Member, **changes) -> Member:
    """
    Update the editable profile fields.

    Email and date of birth are not editable here: email is the verified login
    identity, and date of birth is the basis of the age check.
    """
    fields = [name for name in EDITABLE_FIELDS if name in changes]
    for name in fields:
        setattr(member, name, changes[name])
    if fields:
        member.save(update_fields=[*fields, "updated_at"])
    return member


def change_password(request, member: Member, new_password: str) -> None:
    """Set a new password and keep the current session signed in."""
    member.set_password(new_password)
    member.save(update_fields=["password", "updated_at"])
    update_session_auth_hash(request, member)
