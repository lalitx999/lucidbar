"""
Seed the 12 wheel segments from the original portal (text only, no emoji).
All weights start equal, like the original random choice; managers can
change them from the dashboard.
"""

from django.db import migrations

PRIZES = [
    ("The Crown", "Premium bottle and mixers", "3,500 THB or cash"),
    ("Lucid Credit", "3,000 Lucid credit", "3,000 THB or cash"),
    ("Champagne and Wine", "Champagne and red wine bottle", "3,000 THB or cash"),
    ("Lady's Night", "10 lady drinks", "2,000 THB or cash"),
    ("Double Trouble", "Premium bottle and 5 lady drinks", "4,500 THB or cash"),
    ("VIP Night", "VIP experience package", "5,000 THB or cash"),
    ("Tattoo Voucher", "Tattoo voucher", "Up to 5,000 THB or cash"),
    ("Two Bottles", "2 house bottles and mixers", "5,000 THB or cash"),
    ("The Oracle", "Mystery premium prize", "5,000+ THB or cash"),
    ("Gym Membership", "Gym membership", "Up to 3,000 THB or cash"),
    ("Jackpot", "10,000 Lucid credit", "10,000 THB or cash"),
    ("The Chosen", "Ultimate Lucid experience", "20,000 THB or cash"),
]


def seed(apps, schema_editor):
    WheelPrize = apps.get_model("reveal", "WheelPrize")
    if WheelPrize.objects.exists():
        return
    WheelPrize.objects.bulk_create(
        WheelPrize(label=label, description=description, value_text=value, weight=1, sort_order=i)
        for i, (label, description, value) in enumerate(PRIZES)
    )


class Migration(migrations.Migration):
    dependencies = [("reveal", "0001_initial")]

    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
