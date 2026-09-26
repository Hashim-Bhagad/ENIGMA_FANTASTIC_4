import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import get_session
from app.errors import ApiError
from app.models import Profile, User, now
from app.rate_limit import rate_limit
from app.schemas import Credentials, GuideRequest, Login, ProfileData, ProfileWrite
from app.security import DUMMY_HASH, create_token, current_user, passwords
from app.services.guide import make_guide

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["accounts and profiles"])

AUTH_LIMIT = Depends(rate_limit("auth", 10, 60, "ip"))


def identity(user: User):
    return {"id": user.id, "email": user.email}


def profile_response(profile: Profile):
    return {"id": profile.id, "version": profile.version, "data": profile.data}


def owned_profile(session: Session, owner_id: str, profile_id: str | None = None):
    statement = select(Profile).where(Profile.owner_id == owner_id)
    if profile_id:
        # Request bodies carry UUID objects; the column stores the canonical string form.
        statement = statement.where(Profile.id == str(profile_id))
    profile = session.scalar(statement)
    if profile is None:
        raise HTTPException(404, "Saved profile not found; complete onboarding")
    return profile


@router.post("/auth/register", status_code=201, dependencies=[AUTH_LIMIT])
def register(body: Credentials, session: Session = Depends(get_session)):
    """Create an account. Open route; rate-limited per client IP, never logs credentials."""
    user = User(email=str(body.email).lower(), password_hash=passwords.hash(body.password))
    session.add(user)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        logger.info("registration rejected: email already exists")
        raise HTTPException(409, "An account with that email already exists") from exc
    logger.info("account registered id=%s", user.id)
    return {"user": identity(user), "access_token": create_token(user.id), "token_type": "bearer"}


@router.post("/auth/login", dependencies=[AUTH_LIMIT])
def login(body: Login, session: Session = Depends(get_session)):
    """Exchange credentials for a token. Open route; rate-limited per client IP.

    Credentials are never logged; only the outcome is recorded.
    """
    user = session.scalar(select(User).where(User.email == str(body.email).lower()))
    verified = passwords.verify(body.password, user.password_hash if user else DUMMY_HASH)
    if user is None or not verified:
        logger.info("login rejected")
        raise HTTPException(401, "Email or password is incorrect")
    return {"user": identity(user), "access_token": create_token(user.id), "token_type": "bearer"}


@router.get("/auth/me")
def me(user: User = Depends(current_user)):
    return identity(user)


@router.get("/profiles/me")
def get_profile(user: User = Depends(current_user), session: Session = Depends(get_session)):
    return profile_response(owned_profile(session, user.id))


@router.put("/profiles/me")
def save_profile(
    body: ProfileWrite, user: User = Depends(current_user), session: Session = Depends(get_session)
):
    """Create or update the saved profile.

    A payload identical to the stored profile is a retry of an already-applied
    save: it returns the current profile without bumping ``version``. A
    different payload whose ``expected_version`` is stale is rejected with 409
    ``profile_version_stale``.
    """
    profile = session.scalar(select(Profile).where(Profile.owner_id == user.id))
    incoming = body.data.model_dump(mode="json")
    if profile is None:
        if body.expected_version is not None:
            raise ApiError(
                409, "profile_version_stale", "No profile exists at the supplied version"
            )
        profile = Profile(owner_id=user.id, data=incoming, version=1)
        session.add(profile)
    elif incoming == profile.data:
        return profile_response(profile)
    elif body.expected_version != profile.version:
        session.rollback()
        raise ApiError(409, "profile_version_stale", "Profile changed; reload it before saving")
    else:
        updated = session.execute(
            update(Profile)
            .where(Profile.id == profile.id, Profile.version == body.expected_version)
            .values(data=incoming, version=Profile.version + 1, updated_at=now())
        )
        if updated.rowcount != 1:
            session.rollback()
            raise ApiError(409, "profile_version_stale", "Profile changed; reload it before saving")
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise ApiError(
            409, "profile_version_stale", "Profile changed; reload it before saving"
        ) from exc
    session.refresh(profile)
    return profile_response(profile)


@router.post("/profiles/guide")
def guide(
    body: GuideRequest, user: User = Depends(current_user), session: Session = Depends(get_session)
):
    profile = owned_profile(session, user.id, body.profile_id)
    if profile.version != body.profile_version:
        raise HTTPException(409, "Profile changed; reload before requesting guidance")
    return {
        "profile_id": profile.id,
        "profile_version": profile.version,
        **make_guide(ProfileData.model_validate(profile.data)),
    }
