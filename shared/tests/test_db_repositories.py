"""Tests for repository classes."""

import datetime
import uuid

import pytest
from sqlalchemy.orm import Session

from shared.db.models import Notification, NotificationTemplate, UserPreference
from shared.db.repositories import (
    NotificationRepository,
    TemplateRepository,
    UserPreferenceRepository,
)
from shared.enums import Channel, NotificationStatus, Priority


def _make_notification(**overrides: object) -> Notification:
    """Helper to build a Notification with sensible defaults."""
    defaults: dict = {
        "user_id": uuid.uuid4(),
        "channel": Channel.EMAIL,
        "source_event_id": uuid.uuid4(),
        "source_event_type": "user.registered",
        "content": {"body": "test"},
    }
    defaults.update(overrides)
    return Notification(**defaults)


class TestNotificationRepository:
    def test_create_and_get_by_id(self, db_session: Session) -> None:
        repo = NotificationRepository(db_session)
        n = _make_notification()
        created = repo.create(n)

        fetched = repo.get_by_id(created.id)
        assert fetched is not None
        assert fetched.id == created.id

    def test_get_by_id_not_found(self, db_session: Session) -> None:
        repo = NotificationRepository(db_session)
        assert repo.get_by_id(uuid.uuid4()) is None

    def test_get_by_event_id_and_channel_found(self, db_session: Session) -> None:
        repo = NotificationRepository(db_session)
        event_id = uuid.uuid4()
        n = _make_notification(source_event_id=event_id, channel=Channel.SMS)
        repo.create(n)

        found = repo.get_by_event_id_and_channel(event_id, Channel.SMS)
        assert found is not None
        assert found.source_event_id == event_id

    def test_get_by_event_id_and_channel_not_found(
        self, db_session: Session
    ) -> None:
        repo = NotificationRepository(db_session)
        assert (
            repo.get_by_event_id_and_channel(uuid.uuid4(), Channel.EMAIL) is None
        )

    def test_update_status_to_delivered(self, db_session: Session) -> None:
        repo = NotificationRepository(db_session)
        n = repo.create(_make_notification())
        now = datetime.datetime.now(datetime.UTC)

        updated = repo.update_status(
            n.id, NotificationStatus.DELIVERED, delivered_at=now
        )
        assert updated is not None
        assert updated.status == NotificationStatus.DELIVERED
        assert updated.delivered_at == now

    def test_update_status_increment_attempts(self, db_session: Session) -> None:
        repo = NotificationRepository(db_session)
        n = repo.create(_make_notification())
        assert n.attempts == 0

        updated = repo.update_status(
            n.id, NotificationStatus.FAILED, increment_attempts=True
        )
        assert updated is not None
        assert updated.attempts == 1

    def test_update_status_not_found(self, db_session: Session) -> None:
        repo = NotificationRepository(db_session)
        assert repo.update_status(uuid.uuid4(), NotificationStatus.FAILED) is None

    def test_get_pending_retries_returns_eligible(
        self, db_session: Session
    ) -> None:
        repo = NotificationRepository(db_session)
        now = datetime.datetime.now(datetime.UTC)
        past = now - datetime.timedelta(minutes=5)
        future = now + datetime.timedelta(minutes=5)

        # Eligible: PENDING, next_retry_at in the past, attempts < max
        eligible = _make_notification(
            status=NotificationStatus.PENDING,
            next_retry_at=past,
            attempts=1,
            max_attempts=3,
        )
        repo.create(eligible)

        # Not eligible: next_retry_at in the future
        not_yet = _make_notification(
            status=NotificationStatus.PENDING,
            next_retry_at=future,
            attempts=0,
        )
        repo.create(not_yet)

        # Not eligible: attempts exhausted
        exhausted = _make_notification(
            status=NotificationStatus.FAILED,
            next_retry_at=past,
            attempts=3,
            max_attempts=3,
        )
        repo.create(exhausted)

        results = repo.get_pending_retries(now)
        assert len(results) == 1
        assert results[0].id == eligible.id

    def test_get_pending_retries_respects_limit(
        self, db_session: Session
    ) -> None:
        repo = NotificationRepository(db_session)
        now = datetime.datetime.now(datetime.UTC)
        past = now - datetime.timedelta(minutes=1)

        for _ in range(5):
            repo.create(
                _make_notification(
                    status=NotificationStatus.PENDING,
                    next_retry_at=past,
                    attempts=0,
                )
            )

        results = repo.get_pending_retries(now, limit=2)
        assert len(results) == 2

    def test_get_pending_retries_ordered_by_next_retry_at(
        self, db_session: Session
    ) -> None:
        repo = NotificationRepository(db_session)
        now = datetime.datetime.now(datetime.UTC)

        older = _make_notification(
            status=NotificationStatus.PENDING,
            next_retry_at=now - datetime.timedelta(minutes=10),
            attempts=0,
        )
        newer = _make_notification(
            status=NotificationStatus.PENDING,
            next_retry_at=now - datetime.timedelta(minutes=1),
            attempts=0,
        )
        repo.create(newer)
        repo.create(older)

        results = repo.get_pending_retries(now)
        assert len(results) == 2
        assert results[0].id == older.id
        assert results[1].id == newer.id

    def test_get_channels_by_event_id(self, db_session: Session) -> None:
        repo = NotificationRepository(db_session)
        event_id = uuid.uuid4()

        # No notifications yet
        assert repo.get_channels_by_event_id(event_id) == set()

        # Create notifications for two channels
        repo.create(
            _make_notification(source_event_id=event_id, channel=Channel.EMAIL)
        )
        repo.create(
            _make_notification(source_event_id=event_id, channel=Channel.SMS)
        )

        channels = repo.get_channels_by_event_id(event_id)
        assert channels == {Channel.EMAIL, Channel.SMS}

    def test_get_channels_by_event_id_ignores_other_events(
        self, db_session: Session
    ) -> None:
        repo = NotificationRepository(db_session)
        event_a = uuid.uuid4()
        event_b = uuid.uuid4()

        repo.create(
            _make_notification(source_event_id=event_a, channel=Channel.EMAIL)
        )
        repo.create(
            _make_notification(source_event_id=event_b, channel=Channel.PUSH)
        )

        assert repo.get_channels_by_event_id(event_a) == {Channel.EMAIL}

    def test_idempotency_check_pattern(self, db_session: Session) -> None:
        """Simulate the idempotency pattern used by Notification Service."""
        repo = NotificationRepository(db_session)
        event_id = uuid.uuid4()

        # First time: no existing notification, create one
        existing = repo.get_by_event_id_and_channel(event_id, Channel.EMAIL)
        assert existing is None
        repo.create(
            _make_notification(source_event_id=event_id, channel=Channel.EMAIL)
        )

        # Second time: already exists, skip
        existing = repo.get_by_event_id_and_channel(event_id, Channel.EMAIL)
        assert existing is not None


class TestTemplateRepository:
    def test_get_by_event_type_and_channel(self, db_session: Session) -> None:
        repo = TemplateRepository(db_session)
        t = NotificationTemplate(
            event_type="user.registered",
            channel=Channel.EMAIL,
            subject_template="Welcome",
            body_template="Hello {{ email }}",
        )
        db_session.add(t)
        db_session.flush()

        found = repo.get_by_event_type_and_channel("user.registered", Channel.EMAIL)
        assert found is not None
        assert found.body_template == "Hello {{ email }}"

    def test_inactive_template_not_returned(self, db_session: Session) -> None:
        repo = TemplateRepository(db_session)
        t = NotificationTemplate(
            event_type="order.completed",
            channel=Channel.SMS,
            body_template="Order ready",
            is_active=False,
        )
        db_session.add(t)
        db_session.flush()

        assert (
            repo.get_by_event_type_and_channel("order.completed", Channel.SMS)
            is None
        )

    def test_get_active_templates_for_event(self, db_session: Session) -> None:
        repo = TemplateRepository(db_session)
        for ch in [Channel.EMAIL, Channel.SMS, Channel.PUSH]:
            db_session.add(
                NotificationTemplate(
                    event_type="user.registered",
                    channel=ch,
                    body_template=f"Template for {ch}",
                )
            )
        db_session.flush()

        templates = repo.get_active_templates_for_event("user.registered")
        assert len(templates) == 3
        channels = [t.channel for t in templates]
        assert channels == sorted(channels)

    def test_get_active_templates_excludes_inactive(
        self, db_session: Session
    ) -> None:
        repo = TemplateRepository(db_session)
        db_session.add(
            NotificationTemplate(
                event_type="payment.failed",
                channel=Channel.EMAIL,
                body_template="active",
                is_active=True,
            )
        )
        db_session.add(
            NotificationTemplate(
                event_type="payment.failed",
                channel=Channel.SMS,
                body_template="inactive",
                is_active=False,
            )
        )
        db_session.flush()

        templates = repo.get_active_templates_for_event("payment.failed")
        assert len(templates) == 1
        assert templates[0].channel == Channel.EMAIL


class TestUserPreferenceRepository:
    def test_create_default(self, db_session: Session) -> None:
        repo = UserPreferenceRepository(db_session)
        uid = uuid.uuid4()
        pref = repo.create_default(uid)

        assert pref.user_id == uid
        assert pref.channels == ["email", "sms", "push"]
        assert pref.timezone == "UTC"

    def test_get_by_user_id_found(self, db_session: Session) -> None:
        repo = UserPreferenceRepository(db_session)
        uid = uuid.uuid4()
        repo.create_default(uid)

        fetched = repo.get_by_user_id(uid)
        assert fetched is not None
        assert fetched.user_id == uid

    def test_get_by_user_id_not_found(self, db_session: Session) -> None:
        repo = UserPreferenceRepository(db_session)
        assert repo.get_by_user_id(uuid.uuid4()) is None
