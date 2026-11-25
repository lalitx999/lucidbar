"""Server-side QR rendering as inline SVG (no JavaScript, no external service)."""

from io import BytesIO

import qrcode
import qrcode.image.svg


def render_svg(payload: str, *, border: int = 2) -> str:
    """Return a standalone <svg> element (no XML declaration)."""
    code = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, border=border)
    code.add_data(payload)
    code.make(fit=True)
    image = code.make_image(image_factory=qrcode.image.svg.SvgPathImage)
    buffer = BytesIO()
    image.save(buffer)
    svg = buffer.getvalue().decode("utf-8")
    # Drop the XML declaration so the markup can sit inside HTML.
    return svg[svg.index("<svg") :]
