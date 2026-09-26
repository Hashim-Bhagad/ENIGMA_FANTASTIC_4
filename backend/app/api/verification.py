from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from app.integrations.off import ProviderError
from app.models import User
from app.rate_limit import rate_limit
from app.security import current_user

router = APIRouter(
    prefix="/api/verification",
    tags=["verification"],
    dependencies=[Depends(current_user)],
)


class FssaiVerificationRequest(BaseModel):
    fssai_number: str = Field(pattern=r"^[0-9]{14}$")


@router.post(
    "/fssai",
    dependencies=[Depends(rate_limit("provider_reads", 30, 60, "user"))],
)
async def verify_fssai(
    payload: FssaiVerificationRequest,
    request: Request,
    _user: User = Depends(current_user),
):
    """Verify a 14-digit FSSAI license through TheVerifico."""
    try:
        return await request.app.state.fssai.verify(payload.fssai_number)
    except ProviderError as exc:
        raise HTTPException(503, str(exc)) from exc
