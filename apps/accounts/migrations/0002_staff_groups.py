"""
Staff roles as Django groups:
- Staff: day-to-day club work (hand-overs, check-in). Any is_staff account.
- Manager: also runs the weekly draw, sends broadcasts, decides payments.
Membership of the Manager group is managed by the superuser in Django Admin.
"""

from django.db import migrations

GROUPS = ["Staff", "Manager"]


def create_groups(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    for name in GROUPS:
        Group.objects.get_or_create(name=name)


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0001_initial"),
        ("auth", "0012_alter_user_first_name_max_length"),
    ]

    operations = [migrations.RunPython(create_groups, migrations.RunPython.noop)]
