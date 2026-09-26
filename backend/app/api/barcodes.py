"""Decode a barcode from an uploaded image.

Web has no camera scanner, and photographing a barcode is often easier than typing 13 digits
on a phone, so both clients can send a picture and get the number back.
"""

import io
import logging

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from PIL import Image, UnidentifiedImageError

from app.rate_limit import rate_limit
from app.security import current_user
from app.services.barcodes import decode_barcodes

logger = logging.getLogger(__name__)

MAX_IMAGE_BYTES = 8 * 1024 * 1024

router = APIRouter(prefix="/api/barcodes", tags=["barcode decoding"])


@router.post(
    "/scan",
    dependencies=[
        Depends(current_user),
        Depends(rate_limit("barcode_scan", 20, 60, "user")),
    ],
)
async def scan_barcode(file: UploadFile):
    """Return the retail barcode in a photo. Requires a bearer token."""
    content = await file.read(MAX_IMAGE_BYTES + 1)
    if len(content) > MAX_IMAGE_BYTES:
        raise HTTPException(
            413,
            f"Image is {len(content) / 1048576:.1f} MB; the limit is "
            f"{MAX_IMAGE_BYTES // 1048576} MB. Retake it at a lower resolution.",
        )
    if not content:
        raise HTTPException(422, "The uploaded image was empty; choose it again")
    try:
        with Image.open(io.BytesIO(content)) as image:
            image.verify()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        logger.info("barcode scan rejected bytes=%s reason=%s", len(content), type(exc).__name__)
        raise HTTPException(
            422, f"That file is not a readable image ({len(content)} bytes)"
        ) from exc

    results = decode_barcodes(content)
    if not results:
        raise HTTPException(
            422,
            "No barcode found in that image. Get closer, use more light, or type the digits.",
        )
    best, *alternatives = results
    return {
        "barcode": best["barcode"],
        "format": best["format"],
        "alternatives": alternatives,
        "message": "Barcode read from the image; look it up to see the product record.",
    }
