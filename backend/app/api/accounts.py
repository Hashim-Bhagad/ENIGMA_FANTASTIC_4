from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import get_session
from app.models import Profile, User, now
from app.schemas import Credentials, GuideRequest, Login, ProfileData, ProfileWrite
from app.security import DUMMY_HASH, create_token, current_user, passwords
from app.services.guide import make_guide

router = APIRouter(prefix="/api", tags=["accounts and profiles"])


def identity(user: User):
    return {"id": user.id, "email": user.email}


def profile_response(profile: Profile):
    return {"id": profile.id, "version": profile.version, "data": profile.data}


def owned_profile(session: Session, owner_id: str, profile_id: str | None = None):
    statement = select(Profile).where(Profile.owner_id == owner_id)
    if profile_id:
        statement = statement.where(Profile.id == profile_id)
    profile = session.scalar(statement)
    if profile is None:
        raise HTTPException(404, "Saved profile not found; complete onboarding")
    return profile


@router.post("/auth/register", status_code=201)
def register(body: Credentials, session: Session = Depends(get_session)):
    user = User(email=str(body.email).lower(), password_hash=passwords.hash(body.password))
    session.add(user)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(409, "An account with that email already exists") from exc
    return {"user": identity(user), "access_token": create_token(user.id), "token_type": "bearer"}


@router.post("/auth/login")
def login(body: Login, session: Session = Depends(get_session)):
    user = session.scalar(select(User).where(User.email == str(body.email).lower()))
    verified = passwords.verify(body.password, user.password_hash if user else DUMMY_HASH)
    if user is None or not verified:
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
    profile = session.scalar(select(Profile).where(Profile.owner_id == user.id))
    if profile is None:
        if body.expected_version is not None:
            raise HTTPException(409, "No profile exists at the supplied version")
        profile = Profile(owner_id=user.id, data=body.data.model_dump(mode="json"), version=1)
        session.add(profile)
    else:
        if body.expected_version != profile.version:
            raise HTTPException(409, "Profile changed; reload it before saving")
        updated = session.execute(
            update(Profile)
            .where(Profile.id == profile.id, Profile.version == body.expected_version)
            .values(
                data=body.data.model_dump(mode="json"),
                version=Profile.version + 1,
                updated_at=now(),
            )
        )
        if updated.rowcount != 1:
            session.rollback()
            raise HTTPException(409, "Profile changed; reload it before saving")
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(409, "Profile changed; reload it before saving") from exc
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
