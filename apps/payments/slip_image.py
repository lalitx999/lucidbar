"""
Validate and normalise an uploaded slip image.

The upload is decoded with Pillow and re-encoded as a fresh JPEG. That drops
EXIF/location data and anything smuggled inside the file (polyglots), and it
caps the size so it stays under EasySlip's 4 MB limit.
"""

import hashlib
from dataclasses import dataclass
from io import BytesIO

from django.conf import settings
from django.utils.translation import gettext as _
from PIL import Image, ImageOps, UnidentifiedImageError

ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}
MAX_PIXELS = 40_000_000  # refuse decompression bombs early
MAX_SIDE = 2000  # plenty for QR reading


class SlipImageError(Exception):
    """User-safe message about why the image was refused."""


@dataclass(frozen=True)
class CleanSlip:
    content: bytes
    sha256: str  # hash of the original upload, used to spot re-uploads


def clean_slip(uploaded) -> CleanSlip:
    if uploaded.size > settings.SLIP_MAX_BYTES * 2:
        raise SlipImageError(_("The image is too large. Please upload a screenshot under 8 MB."))
    raw = uploaded.read()
    original_hash = hashlib.sha256(raw).hexdigest()

    try:
        with Image.open(BytesIO(raw)) as probe:
            fmt = probe.format
            width, height = probe.size
            probe.verify()
    except (UnidentifiedImageError, OSError, SyntaxError):
        raise SlipImageError(_("This file is not a valid image.")) from None

    if fmt not in ALLOWED_FORMATS:
        raise SlipImageError(_("Please upload a JPG, PNG or WEBP image."))
    if width * height > MAX_PIXELS:
        raise SlipImageError(_("The image dimensions are too large."))

    # verify() leaves the image unusable, so open it again to convert.
    with Image.open(BytesIO(raw)) as img:
        img = ImageOps.exif_transpose(img)
        img = img.convert("RGB")
        img.thumbnail((MAX_SIDE, MAX_SIDE))
        out = BytesIO()
        img.save(out, format="JPEG", quality=88, optimize=True)

    content = out.getvalue()
    if len(content) > settings.SLIP_MAX_BYTES:
        raise SlipImageError(_("The image is too large after processing. Please upload a clearer screenshot."))
    return CleanSlip(content=content, sha256=original_hash)
