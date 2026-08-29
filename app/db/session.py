from collections.abc import Generator
from functools import lru_cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings


@lru_cache
def get_engine() -> Engine:
    database_url = get_settings().sqlalchemy_database_url
    if not database_url:
        raise RuntimeError("DATABASE_URL is not configured")
    return create_engine(database_url, pool_pre_ping=True)


def create_session() -> Session:
    session_factory = sessionmaker(bind=get_engine(), autoflush=False, expire_on_commit=False)
    return session_factory()


def get_db() -> Generator[Session, None, None]:
    with create_session() as session:
        yield session
