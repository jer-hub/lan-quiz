"""QR code generation helpers."""

from __future__ import annotations

import base64
import io

import qrcode
from qrcode.image.pil import PilImage


def generate_qr_data_url(url: str) -> str:
    """Return a PNG data URL for the given join URL."""
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=8,
        border=2,
    )
    qr.add_data(url)
    qr.make(fit=True)
    img: PilImage = qr.make_image(fill_color="#0F172A", back_color="#FFFFFF")
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded}"
