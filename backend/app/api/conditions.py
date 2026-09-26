"""Condition registry lookup.

The registry is data, not code paths: adding a condition is a registry entry, and the
guide and assessment read whatever the registry exposes.
"""

from fastapi import APIRouter, Depends

from app.schemas import ConditionRegistry
from app.security import current_user
from app.services.conditions import registry_payload

router = APIRouter(prefix="/api", tags=["condition registry"], dependencies=[Depends(current_user)])


@router.get("/conditions", response_model=ConditionRegistry)
def conditions():
    """The versioned condition/alias vocabulary used by the profile and the plan."""
    return registry_payload()
