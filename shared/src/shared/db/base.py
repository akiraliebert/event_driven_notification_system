"""Database foundation: declarative base class, engine and session factories."""

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy ORM models."""


def create_db_engine(dsn: str, **kwargs: object) -> Engine:
    """Create a SQLAlchemy engine from a DSN string.

    Services should pass ``pool_pre_ping=True`` in production to handle
    stale connections after PostgreSQL restarts.
    """
    return create_engine(dsn, **kwargs)


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    """Create a sessionmaker bound to the given engine.

    ``expire_on_commit=False`` prevents detached-instance errors in
    Flask request / Celery task lifecycles where the session is closed
    right after commit.
    """
    return sessionmaker(bind=engine, expire_on_commit=False)
