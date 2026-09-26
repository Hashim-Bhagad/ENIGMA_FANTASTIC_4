from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    pass


def make_engine(url: str):
    options = {"connect_args": {"check_same_thread": False}} if url.startswith("sqlite") else {}
    return create_engine(url, pool_pre_ping=True, **options)


def get_session():
    # Initialization happens on first request, not while importing app modules.
    factory = _session_factory(get_settings().database_url)
    with factory() as session:
        yield session


@lru_cache
def _session_factory(url: str):
    return sessionmaker(bind=make_engine(url), expire_on_commit=False)
