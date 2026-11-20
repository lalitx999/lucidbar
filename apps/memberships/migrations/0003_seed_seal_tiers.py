"""
Seed the three Seal tiers from the original portal. Values can be changed
later from the dashboard; this only creates them if missing.
"""

from django.db import migrations

TIERS = [
    {
        "code": "bronze",
        "name": "Bronze Seal",
        "tagline": "Introductory membership",
        "price_satang": 0,
        "period_days": 0,
        "initial_keys": 2,
        "benefits": "Member QR card\nWeekly Reveal entry\nTreasures catalogue access",
        "sort_order": 10,
    },
    {
        "code": "gold",
        "name": "Gold Seal",
        "tagline": "Priority seating and lounge access",
        "price_satang": 49900,
        "period_days": 30,
        "initial_keys": 10,
        "benefits": "Priority seating\nLounge access\nWeekly Reveal entry",
        "sort_order": 20,
    },
    {
        "code": "obsidian",
        "name": "Black Obsidian Seal",
        "tagline": "Ultimate privileges and private salon entry",
        "price_satang": 99000,
        "period_days": 30,
        "initial_keys": 30,
        "benefits": "Private salon entry\nPriority seating and lounge access\nWeekly Reveal entry",
        "sort_order": 30,
    },
]


def seed(apps, schema_editor):
    SealTier = apps.get_model("memberships", "SealTier")
    for tier in TIERS:
        SealTier.objects.get_or_create(code=tier["code"], defaults=tier)


class Migration(migrations.Migration):
    dependencies = [("memberships", "0002_initial")]

    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
