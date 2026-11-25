"""Re-encode uploaded pictures (treasure photos) as clean JPEGs with Pillow."""

from io import BytesIO

from django.core.files.base import ContentFile
from django.utils.translation import gettext as _
from PIL import Image, ImageOps, UnidentifiedImageError

ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}
MAX_UPLOAD_BYTES = 8 * 1024 * 1024
MAX_PIXELS = 40_000_000


class ImageError(Exception):
    """User-safe message."""


def clean_picture(uploaded, *, max_side: int = 1200) -> ContentFile:
    if uploaded.size > MAX_UPLOAD_BYTES:
        raise ImageError(_("The image is too large. Please upload one under 8 MB."))
    raw = uploaded.read()
    try:
        with Image.open(BytesIO(raw)) as probe:
            fmt = probe.format
            width, height = probe.size
            probe.verify()
    except (UnidentifiedImageError, OSError, SyntaxError):
        raise ImageError(_("This file is not a valid image.")) from None
    if fmt not in ALLOWED_FORMATS:
        raise ImageError(_("Please upload a JPG, PNG or WEBP image."))
    if width * height > MAX_PIXELS:
        raise ImageError(_("The image dimensions are too large."))
    with Image.open(BytesIO(raw)) as img:
        img = ImageOps.exif_transpose(img).convert("RGB")
        img.thumbnail((max_side, max_side))
        out = BytesIO()
        img.save(out, format="JPEG", quality=85, optimize=True)
    return ContentFile(out.getvalue(), name="picture.jpg")
