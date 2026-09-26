"""Personal intake plan.

The plan is read-only: it proposes targets with their evidence and never writes a limit.
Recording a limit stays the effect of saving the profile.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.accounts import owned_profile
from app.db import get_session
from app.errors import ApiError
from app.models import User
from app.schemas import IntakePlan, IntakePlanRequest, ProfileData
from app.security import current_user
from app.services.intake import build_plan
from app.services.labs import confirmed_reports

router = APIRouter(prefix="/api", tags=["personal intake"], dependencies=[Depends(current_user)])


@router.post("/intake/plan", response_model=IntakePlan)
def intake_plan(
    body: IntakePlanRequest,
    user: User = Depends(current_user),
    session: Session = Depends(get_session),
):
    """Baseline intakes plus targets derived from confirmed reports and conditions."""
    profile = owned_profile(session, user.id, str(body.profile_id))
    if profile.version != body.profile_version:
        raise ApiError(
            409,
            "profile_version_stale",
            "Profile changed; reload before building an intake plan",
        )
    data = ProfileData.model_validate(profile.data)
    return build_plan(data, confirmed_reports(session, user.id))
