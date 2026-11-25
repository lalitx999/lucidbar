"""Creating and editing treasures from the dashboard."""

from django.db import transaction

from apps.audit.services import audit_service
from apps.core.images import clean_picture

from ..models import Treasure

FIELDS = ("name", "category", "description", "keys_cost", "stock", "is_featured", "is_active", "sort_order")


def save(manager, treasure: Treasure | None = None, *, image=None, remove_image=False, **values) -> Treasure:
    """Create (treasure=None) or update. `image` is an uploaded file; it is re-encoded first."""
    picture = clean_picture(image) if image else None  # may raise ImageError before any write
    with transaction.atomic():
        creating = treasure is None
        if creating:
            treasure = Treasure(**{f: values[f] for f in FIELDS if f in values})
            changes = {f: values[f] for f in FIELDS if f in values}
        else:
            treasure = Treasure.objects.select_for_update().get(pk=treasure.pk)
            changes = {}
            for field in FIELDS:
                if field in values and getattr(treasure, field) != values[field]:
                    changes[field] = f"{getattr(treasure, field)} -> {values[field]}"
                    setattr(treasure, field, values[field])
        old_image = treasure.image.name if treasure.image else ""
        if picture is not None:
            treasure.image.save(picture.name, picture, save=False)
            changes["image"] = "new"
        elif remove_image and old_image:
            treasure.image = ""
            changes["image"] = "removed"
        if creating or changes:
            treasure.save()
            audit_service.record(manager, "treasure.create" if creating else "treasure.update", treasure, **changes)
        if old_image and "image" in changes:
            storage, name = treasure.image.storage, old_image
            transaction.on_commit(lambda: storage.delete(name))
    return treasure
