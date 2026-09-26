import io

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile
from PIL import Image, UnidentifiedImageError

from app.integrations.off import ProviderError
from app.models import User
from app.security import current_user

router = APIRouter(prefix="/api/labels", tags=["label extraction"])


@router.post("/extract")
async def extract(request: Request, file: UploadFile, user: User = Depends(current_user)):
    content = await file.read(5 * 1024 * 1024 + 1)
    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(413, "Image must be at most 5 MB")
    try:
        with Image.open(io.BytesIO(content)) as image:
            if image.format not in {"JPEG", "PNG"} or image.width * image.height > 20_000_000:
                raise ValueError("Unsupported image")
            mime_type = "image/jpeg" if image.format == "JPEG" else "image/png"
            image.verify()
    except (ValueError, UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise HTTPException(422, "Upload a readable JPEG or PNG label photo") from exc
    try:
        food = await request.app.state.models.extract_label(content, mime_type)
    except ProviderError as exc:
        raise HTTPException(503, str(exc)) from exc
    return {"food": food.model_dump(mode="json"), "confirmation_required": True}
