"""Shared test fixtures for database tests (SQLite in-memory)."""

from collections.abc import Generator

import pytest
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session

from shared.db.base import Base


@pytest.fixture(scope="session")
def db_engine() -> Engine:
    """Create a single in-memory SQLite engine for the test session."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return engine


@pytest.fixture()
def db_session(db_engine: Engine) -> Generator[Session, None, None]:
    """Transactional session that rolls back after each test."""
    connection = db_engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection)

    yield session

    session.close()
    if transaction.is_active:
        transaction.rollback()
    connection.close()
