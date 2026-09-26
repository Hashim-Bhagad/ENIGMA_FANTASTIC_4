"""Retail barcode decoding from an uploaded image.

A browser cannot open the phone camera the way the native app does, and a desktop webcam is
awkward for a pack lying on a table, so the client can send a photo or screenshot instead.
Decoding happens here: zxing reads the pixels, and only codes that satisfy our barcode
contract (8, 12, 13 or 14 digits) are returned, so a QR code an image happens to contain is
never treated as a product identifier.
"""

from __future__ import annotations

import io
import re

import zxingcpp
from PIL import Image

BARCODE_PATTERN = re.compile(r"^(?:[0-9]{8}|[0-9]{12,14})$")

# Formats that can carry a retail product code. A QR or DataMatrix payload is ignored even
# when it decodes, because it is not a product identifier and could be any URL or text.
RETAIL_FORMATS = {"EAN-13", "EAN-8", "UPC-A", "UPC-E"}


def decode_barcodes(content: bytes) -> list[dict]:
    """Every retail barcode the image contains, in decode order, deduplicated.

    Returns ``[{"barcode": str, "format": str}]``. An unreadable image or one with no retail
    barcode yields an empty list; the caller decides what to tell the user.
    """
    try:
        with Image.open(io.BytesIO(content)) as image:
            picture = image.convert("RGB")
    except Exception:  # noqa: BLE001 - any decode failure means "no barcode here"
        return []

    found: list[dict] = []
    seen: set[str] = set()
    for result in zxingcpp.read_barcodes(picture):
        text = (result.text or "").strip()
        fmt = str(result.format)
        # zxing reports formats as "BarcodeFormat.EAN_13" in some builds, "EAN-13" in others.
        normalised = fmt.replace("BarcodeFormat.", "").replace("_", "-")
        if normalised not in RETAIL_FORMATS or not result.valid:
            continue
        if not BARCODE_PATTERN.fullmatch(text) or text in seen:
            continue
        seen.add(text)
        found.append({"barcode": text, "format": normalised})
    return found
