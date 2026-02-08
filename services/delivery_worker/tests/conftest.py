"""Test fixtures for delivery_worker tests."""

import uuid
from collections.abc import Generator
from unittest.mock import MagicMock

import pytest
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from shared.db.base import Base
from shared.db.models import Notification
from shared.enums import Channel, NotificationStatus, Priority

from delivery_worker.config import DeliveryConfig, RateLimitConfig
from delivery_worker.providers import ProviderRegistry
from delivery_worker.providers.base import DeliveryResult
from delivery_worker.rate_limiter import RateLimiter
from delivery_worker.status_publisher import KafkaStatusPublisher


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


@pytest.fixture()
def session_factory(db_session: Session) -> MagicMock:
    """Session factory that always returns the test session.

    Wraps db_session so that ``with session_factory() as session:``
    returns our transactional test session.
    """
    factory = MagicMock(spec=sessionmaker)
    ctx = MagicMock()
    ctx.__enter__ = MagicMock(return_value=db_session)
    ctx.__exit__ = MagicMock(return_value=False)
    factory.return_value = ctx
    return factory


@pytest.fixture()
def mock_rate_limiter() -> MagicMock:
    """Rate limiter that always allows."""
    limiter = MagicMock(spec=RateLimiter)
    limiter.acquire.return_value = True
    return limiter


@pytest.fixture()
def mock_status_publisher() -> MagicMock:
    return MagicMock(spec=KafkaStatusPublisher)


@pytest.fixture()
def mock_provider_registry() -> MagicMock:
    """Provider registry returning a successful stub provider."""
    registry = MagicMock(spec=ProviderRegistry)
    provider = MagicMock()
    provider.send.return_value = DeliveryResult(success=True, details="ok")
    registry.get.return_value = provider
    return registry


@pytest.fixture()
def delivery_config() -> DeliveryConfig:
    return DeliveryConfig()


@pytest.fixture()
def sample_notification(db_session: Session) -> Notification:
    """Create a PENDING notification in the test DB."""
    notification = Notification(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        channel=Channel.EMAIL,
        priority=Priority.NORMAL,
        status=NotificationStatus.PENDING,
        source_event_id=uuid.uuid4(),
        source_event_type="user.registered",
        content={"subject": "Welcome!", "body": "Hello!"},
    )
    db_session.add(notification)
    db_session.flush()
    return notification
