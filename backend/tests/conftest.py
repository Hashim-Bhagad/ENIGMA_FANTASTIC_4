"""Test fixtures for both the dependency-free SQLite run and Postgres runs.

Default mode (no ``TEST_DATABASE_URL``) is self-contained: an in-memory SQLite
database is created straight from ``Base.metadata`` so the suite needs no
services. That mode cannot prove locking, JSONB, or type-enforcement contracts.

Postgres mode is the documented path for the contracts SQLite cannot express.
Set ``TEST_DATABASE_URL`` to a throwaway database whose name ends in ``_test``
(the suffix guard prevents ever pointing tests at a real database)::

    docker exec dietary-risk-db-1 psql -U dietary -c 'CREATE DATABASE dietary_test'
    cd backend
    TEST_DATABASE_URL=postgresql+psycopg://dietary:<password>@localhost:5433/dietary_test \\
        uv run pytest -q

In that mode the schema is built by ``alembic upgrade head`` rather than
``create_all``, so a model/migration mismatch surfaces as a real failure
(``tests/test_migrations.py`` checks the drift exhaustively). ``DATABASE_URL``
is pointed at the same test database for the duration of the process so no
in-process Alembic or app code can touch the configured development database.
Each test starts from a clean schema via ``TRUNCATE``.
"""

import os

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

os.environ.setdefault("JWT_SECRET", "test-only-signing-key-at-least-32-characters")
os.environ["FIREWORKS_API_KEY"] = ""
os.environ["TYPESAFE_API_KEY"] = ""

BACKEND_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")

if TEST_DATABASE_URL:
    database_name = TEST_DATABASE_URL.rsplit("/", 1)[-1].split("?", 1)[0]
    if not database_name.endswith("_test"):
        raise ValueError(
            "TEST_DATABASE_URL must point at a dedicated database ending in _test; "
            f"got {database_name!r}"
        )
    # Keep in-process settings (app and Alembic) on the throwaway database.
    os.environ["DATABASE_URL"] = TEST_DATABASE_URL

from app.db import Base, get_session  # noqa: E402
from app.main import create_app  # noqa: E402


def alembic_config() -> Config:
    config = Config(os.path.join(BACKEND_ROOT, "alembic.ini"))
    config.set_main_option("script_location", os.path.join(BACKEND_ROOT, "migrations"))
    config.set_main_option("prepend_sys_path", BACKEND_ROOT)
    config.set_main_option("path_separator", "os")
    return config


def quoted(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def reset_postgres(engine) -> None:
    """Empty every modelled table between tests without dropping the schema."""
    tables = ", ".join(quoted(table.name) for table in Base.metadata.sorted_tables)
    with engine.begin() as connection:
        connection.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))
        # Readiness tests build their own alembic_version state; drop any row the
        # migration run left behind so Postgres mode matches SQLite mode here.
        connection.execute(text("DROP TABLE IF EXISTS alembic_version"))


@pytest.fixture(scope="session")
def postgres_session_engine():
    """Migrated Postgres engine shared by every test, or ``None`` in SQLite mode."""
    if not TEST_DATABASE_URL:
        yield None
        return
    engine = create_engine(TEST_DATABASE_URL, pool_pre_ping=True)
    # The database is dedicated to tests, so rebuild its schema from scratch: this
    # keeps repeat runs and a previously interrupted run deterministic, and
    # ``alembic upgrade head`` (not ``create_all``) is the only schema source.
    with engine.begin() as connection:
        connection.execute(text("DROP SCHEMA public CASCADE"))
        connection.execute(text("CREATE SCHEMA public"))
    command.upgrade(alembic_config(), "head")
    yield engine
    engine.dispose()


@pytest.fixture
def db_engine(postgres_session_engine):
    if TEST_DATABASE_URL:
        reset_postgres(postgres_session_engine)
        yield postgres_session_engine
        return
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def postgres_engine(db_engine):
    """The migrated Postgres engine, or a clean skip in the default SQLite run."""
    if not TEST_DATABASE_URL:
        pytest.skip("Postgres-only contract: set TEST_DATABASE_URL to a *_test database")
    return db_engine


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
