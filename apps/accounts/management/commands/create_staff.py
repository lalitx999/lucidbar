"""
Create (or promote) a staff account for the dashboard, without Django Admin.

    python manage.py create_staff door@example.com --name "Door Team" --phone 812345678
    python manage.py create_staff boss@example.com --name "Club Manager" --phone 898765432 --manager

The password is asked for interactively (never pass it on the command line,
where it would end up in the shell history). An existing account keeps its
password unless --reset-password is given.
"""

import getpass
import secrets

from django.contrib.auth.models import Group
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import Member
from apps.core.decorators import MANAGER_GROUP

STAFF_GROUP = "Staff"


class Command(BaseCommand):
    help = "Create or promote a Staff (or Manager) dashboard account."

    def add_arguments(self, parser):
        parser.add_argument("email")
        parser.add_argument("--name", required=True, help="Full name shown in the dashboard and audit log")
        parser.add_argument("--phone", required=True, help="Mobile number without the country code")
        parser.add_argument("--country-code", default="+66")
        parser.add_argument("--manager", action="store_true", help="Also add to the Manager group")
        parser.add_argument("--reset-password", action="store_true")

    def _ask_password(self, email):
        for _ in range(3):
            first = getpass.getpass(f"Password for {email}: ")
            if first != getpass.getpass("Password (again): "):
                self.stderr.write("Passwords do not match.")
                continue
            try:
                validate_password(first)
            except ValidationError as exc:
                self.stderr.write(" ".join(exc.messages))
                continue
            return first
        raise CommandError("No valid password given.")

    def handle(self, *args, **opts):
        email = opts["email"].strip().lower()
        member = Member.objects.filter(email__iexact=email).first()
        password = None
        if member is None or opts["reset_password"]:
            password = self._ask_password(email)

        with transaction.atomic():
            if member is None:
                member = Member.objects.create_user(
                    email=email,
                    password=password,
                    full_name=opts["name"],
                    handle="staff_" + secrets.token_hex(3),
                    country_code=opts["country_code"],
                    phone=opts["phone"],
                    status=Member.Status.ACTIVE,
                    email_verified_at=timezone.now(),
                    is_staff=True,
                )
                created = True
            else:
                member.is_staff = True
                member.full_name = opts["name"]
                if password:
                    member.set_password(password)
                member.save()
                created = False
            member.groups.add(Group.objects.get_or_create(name=STAFF_GROUP)[0])
            if opts["manager"]:
                member.groups.add(Group.objects.get_or_create(name=MANAGER_GROUP)[0])

        role = "Manager" if opts["manager"] else "Staff"
        self.stdout.write(self.style.SUCCESS(f"{'Created' if created else 'Updated'} {role} account {email}"))
