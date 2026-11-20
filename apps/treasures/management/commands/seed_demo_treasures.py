"""
Create a few sample treasures for local development and demos.
Not run by migrations, so production starts with an empty catalogue.
"""

from django.core.management.base import BaseCommand

from apps.treasures.models import Treasure

DEMO = [
    ("Premium whisky pour", Treasure.Category.SPIRITS, 4, "A double pour of the house premium whisky.", True),
    ("Champagne bottle", Treasure.Category.SPIRITS, 25, "A bottle of champagne served at your table.", False),
    ("Hand-rolled cigar", Treasure.Category.CIGARS, 6, "A hand-rolled cigar from the humidor.", False),
    ("VIP lounge pass", Treasure.Category.EXPERIENCES, 15, "One evening in the VIP lounge for you and a guest.", False),
    ("Private table reservation", Treasure.Category.EXPERIENCES, 30, "A reserved private table for the night.", False),
    ("Lucid Society cap", Treasure.Category.MERCHANDISE, 8, "Limited-edition black and gold cap.", False),
]


class Command(BaseCommand):
    help = "Create sample treasures (idempotent, local development only)."

    def handle(self, *args, **options):
        created = 0
        for order, (name, category, cost, description, featured) in enumerate(DEMO):
            _, was_created = Treasure.objects.get_or_create(
                name=name,
                defaults={
                    "category": category,
                    "keys_cost": cost,
                    "description": description,
                    "is_featured": featured,
                    "sort_order": order,
                },
            )
            created += was_created
        self.stdout.write(self.style.SUCCESS(f"{created} treasures created ({len(DEMO) - created} already existed)."))
