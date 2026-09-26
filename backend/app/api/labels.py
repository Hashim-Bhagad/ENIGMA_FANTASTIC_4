import hashlib
import io
import logging
import re

from fastapi import APIRouter, Depends, Form, HTTPException, Request, UploadFile
from PIL import Image, UnidentifiedImageError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.catalog import store_product
from app.db import get_session
from app.integrations.off import ProviderError
from app.models import Product, User
from app.rate_limit import rate_limit
from app.security import current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/labels", tags=["label extraction"])


@router.post(
    "/extract",
    dependencies=[Depends(rate_limit("label_extract", 10, 60, "user"))],
)
async def extract(
    request: Request,
    file: UploadFile,
    barcode: str | None = Form(default=None),
    name: str | None = Form(default=None),
    user: User = Depends(current_user),
    session: Session = Depends(get_session),
):
    """Extract a label observation from a photo. Requires a bearer token.

    Rate-limited per user. The route keeps its own 5 MiB read cap for the image
    in addition to the global request body cap.

    This is the fallback when a barcode has no record anywhere: the optional ``barcode``
    is attached to the extracted observation and the result is stored as a
    ``label_extraction`` catalog record, so the next lookup of that barcode finds the
    pack you photographed instead of asking again. A reviewed snapshot is never
    overwritten by community data (see ``catalog.store_product``).
    """
    if barcode is not None:
        barcode = barcode.strip()
        if barcode and not re.fullmatch(r"(?:[0-9]{8}|[0-9]{12,14})", barcode):
            raise HTTPException(422, "Enter an 8, 12, 13, or 14 digit barcode")
        barcode = barcode or None
    content = await file.read(5 * 1024 * 1024 + 1)
    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(413, "Image must be at most 5 MB")
    if not content:
        raise HTTPException(422, "The uploaded file was empty; choose the photo again")
    try:
        with Image.open(io.BytesIO(content)) as image:
            detected = image.format
            if detected not in {"JPEG", "PNG"} or image.width * image.height > 20_000_000:
                raise ValueError(detected or "unknown")
            mime_type = "image/jpeg" if detected == "JPEG" else "image/png"
            image.verify()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        logger.info("label upload rejected bytes=%s reason=%s", len(content), type(exc).__name__)
        raise HTTPException(
            422, f"The uploaded file is not a readable JPEG or PNG ({len(content)} bytes)"
        ) from exc
    except ValueError as exc:
        logger.info("label upload rejected bytes=%s format=%s", len(content), exc)
        raise HTTPException(422, f"Upload a JPEG or PNG label photo (received {exc})") from exc
    try:
        food = await request.app.state.models.extract_label(content, mime_type)
    except ProviderError as exc:
        logger.warning("label extraction failed: %s", type(exc).__name__)
        raise HTTPException(503, str(exc)) from exc

    if barcode or (name and name.strip()):
        food = food.model_copy(
            update={
                **({"barcode": barcode} if barcode else {}),
                **({"name": name.strip()[:300]} if name and name.strip() else {}),
            }
        )

    product_id = None
    if barcode:
        # Stable per photo: re-uploading the same label updates one record instead of
        # filling the catalog with duplicates.
        source_id = "label-" + hashlib.sha256(content).hexdigest()[:32]
        try:
            product = store_product(session, food, source_id, {})
            session.commit()
            product_id = product.id
        except IntegrityError:
            session.rollback()
            existing = session.scalar(select(Product).where(Product.barcode == barcode))
            product_id = existing.id if existing else None
            logger.warning("label record for barcode collided; kept the stored row")

    return {
        "food": food.model_dump(mode="json"),
        "confirmation_required": True,
        "saved": product_id is not None,
        "product_id": product_id,
    }
