from datetime import UTC, datetime, timedelta

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pwdlib import PasswordHash
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_session
from app.models import User

passwords = PasswordHash.recommended()
bearer = HTTPBearer(auto_error=False)
DUMMY_HASH = passwords.hash("Dummy password for timing equalization")


def create_token(user_id: str) -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    return jwt.encode(
        {
            "sub": user_id,
            "iat": now,
            "exp": now + timedelta(minutes=settings.token_minutes),
            "iss": "dietary-risk-api",
            "aud": "dietary-risk-client",
        },
        settings.jwt_secret.get_secret_value(),
        algorithm="HS256",
    )


def current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    session: Session = Depends(get_session),
) -> User:
    unauthorized = HTTPException(
        status_code=401, detail="Sign in to continue", headers={"WWW-Authenticate": "Bearer"}
    )
    if credentials is None:
        raise unauthorized
    try:
        claims = jwt.decode(
            credentials.credentials,
            get_settings().jwt_secret.get_secret_value(),
            algorithms=["HS256"],
            audience="dietary-risk-client",
            issuer="dietary-risk-api",
            options={"require": ["sub", "exp", "iat"]},
        )
        user = session.get(User, claims["sub"])
    except (jwt.InvalidTokenError, KeyError, TypeError) as exc:
        raise unauthorized from exc
    if user is None:
        raise unauthorized
    return user
