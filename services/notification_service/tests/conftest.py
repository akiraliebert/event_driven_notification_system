"""Test fixtures for notification_service tests."""

from collections.abc import Generator
from unittest.mock import MagicMock

import pytest
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from shared.db.base import Base
from shared.db.models import NotificationTemplate
from shared.enums import Channel

from notification_service.handler import EventHandler
from notification_service.producer import KafkaStatusProducer


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
def session_factory(db_session: Session) -> sessionmaker[Session]:
    """Session factory that always returns the test session.

    This makes the handler's `with session_factory() as session:` use
    our transactional test session instead of creating a new one.
    """
    factory = MagicMock(spec=sessionmaker)
    ctx = MagicMock()
    ctx.__enter__ = MagicMock(return_value=db_session)
    ctx.__exit__ = MagicMock(return_value=False)
    factory.return_value = ctx
    return factory


@pytest.fixture()
def mock_celery() -> MagicMock:
    return MagicMock()


@pytest.fixture()
def mock_status_producer() -> MagicMock:
    return MagicMock(spec=KafkaStatusProducer)


@pytest.fixture()
def seed_templates(db_session: Session) -> list[NotificationTemplate]:
    """Seed 9 templates (3 event_types x 3 channels)."""
    templates = []
    template_data = [
        ("user.registered", Channel.EMAIL, "Welcome!", "Hello {{ email }}!"),
        ("user.registered", Channel.SMS, None, "Welcome {{ email }}"),
        ("user.registered", Channel.PUSH, None, '{"title": "Welcome!", "body": "Hi"}'),
        ("order.completed", Channel.EMAIL, "Order #{{ order_id[:8] }}", "Total: ${{ total_amount }}"),
        ("order.completed", Channel.SMS, None, "Order #{{ order_id[:8] }} — ${{ total_amount }}"),
        ("order.completed", Channel.PUSH, None, '{"title": "Order", "body": "${{ total_amount }}"}'),
        ("payment.failed", Channel.EMAIL, "Payment issue", "Reason: {{ reason }}"),
        ("payment.failed", Channel.SMS, None, "Payment failed: {{ reason }}"),
        ("payment.failed", Channel.PUSH, None, '{"title": "Payment Failed", "body": "{{ reason }}"}'),
    ]
    for event_type, channel, subject, body in template_data:
        t = NotificationTemplate(
            event_type=event_type,
            channel=channel,
            subject_template=subject,
            body_template=body,
        )
        db_session.add(t)
        templates.append(t)
    db_session.flush()
    return templates


@pytest.fixture()
def handler(
    session_factory: sessionmaker[Session],
    mock_celery: MagicMock,
    mock_status_producer: MagicMock,
) -> EventHandler:
    return EventHandler(
        session_factory=session_factory,
        celery_app=mock_celery,
        status_producer=mock_status_producer,
    )
