import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

os.environ.setdefault("JWT_SECRET", "test-only-signing-key-at-least-32-characters")
os.environ["FIREWORKS_API_KEY"] = ""
os.environ["TYPESAFE_API_KEY"] = ""

from app.db import Base, get_session  # noqa: E402
from app.main import create_app  # noqa: E402


@pytest.fixture
def db_engine():
    url = os.environ.get("TEST_DATABASE_URL")
    if url:
        if not url.rsplit("/", 1)[-1].endswith("_test"):
            raise ValueError("Integration tests require a dedicated database ending in _test")
        engine = create_engine(url)
    else:
        engine = create_engine(
            "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
        )
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def client(db_engine):
    app = create_app()

    def test_session():
        with Session(db_engine, expire_on_commit=False) as session:
            yield session

    app.dependency_overrides[get_session] = test_session
    with TestClient(app) as client:
        yield client


def signup(client, email="first@example.com"):
    response = client.post(
        "/api/auth/register", json={"email": email, "password": "A-test-password-123"}
    )
    assert response.status_code == 201, response.text
    return {"Authorization": "Bearer " + response.json()["access_token"]}
