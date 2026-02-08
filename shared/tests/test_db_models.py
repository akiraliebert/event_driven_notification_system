"""Tests for SQLAlchemy ORM models."""

import uuid

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from shared.db.models import Notification, NotificationTemplate, UserPreference
from shared.enums import Channel, NotificationStatus, Priority, UserEventType


class TestNotificationModel:
    def test_create_with_defaults(self, db_session: Session) -> None:
        n = Notification(
            user_id=uuid.uuid4(),
            channel=Channel.EMAIL,
            source_event_id=uuid.uuid4(),
            source_event_type=UserEventType.REGISTERED,
            content={"subject": "Hello"},
        )
        db_session.add(n)
        db_session.flush()

        assert n.id is not None
        assert n.status == NotificationStatus.PENDING
        assert n.priority == Priority.NORMAL
        assert n.attempts == 0
        assert n.max_attempts == 3
        assert n.next_retry_at is None
        assert n.delivered_at is None
        assert n.failed_reason is None

    def test_create_with_all_fields(self, db_session: Session) -> None:
        nid = uuid.uuid4()
        uid = uuid.uuid4()
        eid = uuid.uuid4()
        n = Notification(
            id=nid,
            user_id=uid,
            channel=Channel.SMS,
            priority=Priority.CRITICAL,
            status=NotificationStatus.SENDING,
            source_event_id=eid,
            source_event_type="order.completed",
            content={"body": "Your order is ready"},
            attempts=1,
            max_attempts=5,
            failed_reason="timeout",
        )
        db_session.add(n)
        db_session.flush()

        fetched = db_session.get(Notification, nid)
        assert fetched is not None
        assert fetched.user_id == uid
        assert fetched.channel == Channel.SMS
        assert fetched.priority == Priority.CRITICAL
        assert fetched.attempts == 1
        assert fetched.max_attempts == 5
        assert fetched.failed_reason == "timeout"

    def test_content_stores_json(self, db_session: Session) -> None:
        content = {"subject": "Test", "body": "Hello {{ name }}", "nested": [1, 2]}
        n = Notification(
            user_id=uuid.uuid4(),
            channel=Channel.PUSH,
            source_event_id=uuid.uuid4(),
            source_event_type="payment.failed",
            content=content,
        )
        db_session.add(n)
        db_session.flush()

        fetched = db_session.get(Notification, n.id)
        assert fetched is not None
        assert fetched.content == content

    def test_unique_constraint_event_id_and_channel(
        self, db_session: Session
    ) -> None:
        event_id = uuid.uuid4()
        base_kwargs = {
            "user_id": uuid.uuid4(),
            "source_event_id": event_id,
            "source_event_type": "user.registered",
            "content": {"body": "hi"},
        }
        db_session.add(Notification(channel=Channel.EMAIL, **base_kwargs))
        db_session.flush()

        db_session.add(Notification(channel=Channel.EMAIL, **base_kwargs))
        with pytest.raises(IntegrityError):
            db_session.flush()

    def test_unique_constraint_allows_different_channels(
        self, db_session: Session
    ) -> None:
        event_id = uuid.uuid4()
        base_kwargs = {
            "user_id": uuid.uuid4(),
            "source_event_id": event_id,
            "source_event_type": "user.registered",
            "content": {"body": "hi"},
        }
        db_session.add(Notification(channel=Channel.EMAIL, **base_kwargs))
        db_session.add(Notification(channel=Channel.SMS, **base_kwargs))
        db_session.flush()  # no error

    def test_nullable_fields(self, db_session: Session) -> None:
        n = Notification(
            user_id=uuid.uuid4(),
            channel=Channel.EMAIL,
            source_event_id=uuid.uuid4(),
            source_event_type="user.registered",
            content={"body": "test"},
        )
        db_session.add(n)
        db_session.flush()

        assert n.next_retry_at is None
        assert n.delivered_at is None
        assert n.failed_reason is None


class TestNotificationTemplateModel:
    def test_create_with_defaults(self, db_session: Session) -> None:
        t = NotificationTemplate(
            event_type="user.registered",
            channel=Channel.EMAIL,
            subject_template="Welcome!",
            body_template="Hello {{ email }}",
        )
        db_session.add(t)
        db_session.flush()

        assert t.id is not None
        assert t.is_active is True
        assert t.created_at is not None

    def test_unique_constraint_event_type_channel(
        self, db_session: Session
    ) -> None:
        base_kwargs = {
            "event_type": "order.completed",
            "channel": Channel.SMS,
            "body_template": "Order confirmed",
        }
        db_session.add(NotificationTemplate(**base_kwargs))
        db_session.flush()

        db_session.add(NotificationTemplate(**base_kwargs))
        with pytest.raises(IntegrityError):
            db_session.flush()

    def test_subject_template_nullable(self, db_session: Session) -> None:
        t = NotificationTemplate(
            event_type="payment.failed",
            channel=Channel.PUSH,
            subject_template=None,
            body_template='{"title": "Payment failed"}',
        )
        db_session.add(t)
        db_session.flush()

        assert t.subject_template is None


class TestUserPreferenceModel:
    def test_create_with_defaults(self, db_session: Session) -> None:
        pref = UserPreference(
            user_id=uuid.uuid4(),
            channels=[Channel.EMAIL, Channel.SMS],
        )
        db_session.add(pref)
        db_session.flush()

        assert pref.timezone == "UTC"
        assert pref.quiet_hours_start is None
        assert pref.quiet_hours_end is None

    def test_channels_stored_as_json_list(self, db_session: Session) -> None:
        uid = uuid.uuid4()
        pref = UserPreference(
            user_id=uid,
            channels=[Channel.EMAIL, Channel.PUSH],
        )
        db_session.add(pref)
        db_session.flush()

        fetched = db_session.get(UserPreference, uid)
        assert fetched is not None
        assert fetched.channels == ["email", "push"]

    def test_duplicate_user_id_raises(self, db_session: Session) -> None:
        uid = uuid.uuid4()
        db_session.add(UserPreference(user_id=uid, channels=["email"]))
        db_session.flush()

        db_session.add(UserPreference(user_id=uid, channels=["sms"]))
        with pytest.raises(IntegrityError):
            db_session.flush()
