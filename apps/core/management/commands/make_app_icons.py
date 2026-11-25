"""
Build the PWA icons from static/img/logo.png with Pillow.

    python manage.py make_app_icons

Writes static/img/pwa/: icon-192.png, icon-512.png, maskable-512.png
(logo inside the 80% safe zone), apple-touch-icon.png (180, no
transparency) and favicon-32.png. Run again whenever the logo changes.
"""

from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from PIL import Image

BACKGROUND = (0, 0, 0)


def _square(logo: Image.Image, size: int, content_ratio: float) -> Image.Image:
    canvas = Image.new("RGB", (size, size), BACKGROUND)
    inner = round(size * content_ratio)
    resized = logo.resize((inner, inner), Image.Resampling.LANCZOS)
    offset = (size - inner) // 2
    canvas.paste(resized, (offset, offset))
    return canvas


class Command(BaseCommand):
    help = "Generate PWA icons from static/img/logo.png"

    def handle(self, *args, **options):
        base = Path(settings.BASE_DIR) / "static" / "img"
        out = base / "pwa"
        out.mkdir(exist_ok=True)
        with Image.open(base / "logo.png") as source:
            logo = source.convert("RGB")
            targets = {
                "icon-192.png": (192, 1.0),
                "icon-512.png": (512, 1.0),
                "maskable-512.png": (512, 0.8),
                "apple-touch-icon.png": (180, 0.9),
                "favicon-32.png": (32, 1.0),
            }
            for name, (size, ratio) in targets.items():
                _square(logo, size, ratio).save(out / name, format="PNG", optimize=True)
                self.stdout.write(f"wrote {out / name}")
