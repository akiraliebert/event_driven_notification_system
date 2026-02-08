"""Tests for the EventHandler — core business logic."""

import datetime
import uuid
from unittest.mock import MagicMock

import pytest
from sqlalchemy.orm import Session

from shared.db.models import Notification, NotificationTemplate, UserPreference
from shared.db.repositories import NotificationRepository
from shared.enums import Channel, NotificationStatus, Priority

from notification_service.handler import EventHandler


def _make_user_registered_event(
    user_id: uuid.UUID | None = None,
    event_id: uuid.UUID | None = None,
) -> dict:
    return {
        "metadata": {
            "event_id": str(event_id or uuid.uuid4()),
            "event_type": "user.registered",
            "occurred_at": datetime.datetime.now(datetime.UTC).isoformat(),
            "version": 1,
        },
        "payload": {
            "user_id": str(user_id or uuid.uuid4()),
            "email": "test@example.com",
        },
    }


def _make_order_completed_event(
    user_id: uuid.UUID | None = None,
    event_id: uuid.UUID | None = None,
) -> dict:
    return {
        "metadata": {
            "event_id": str(event_id or uuid.uuid4()),
            "event_type": "order.completed",
            "occurred_at": datetime.datetime.now(datetime.UTC).isoformat(),
            "version": 1,
        },
        "payload": {
            "user_id": str(user_id or uuid.uuid4()),
            "order_id": str(uuid.uuid4()),
            "total_amount": "99.99",
        },
    }


def _make_payment_failed_event(
    user_id: uuid.UUID | None = None,
    event_id: uuid.UUID | None = None,
) -> dict:
    return {
        "metadata": {
            "event_id": str(event_id or uuid.uuid4()),
            "event_type": "payment.failed",
            "occurred_at": datetime.datetime.now(datetime.UTC).isoformat(),
            "version": 1,
        },
        "payload": {
            "user_id": str(user_id or uuid.uuid4()),
            "payment_id": str(uuid.uuid4()),
            "reason": "Insufficient funds",
        },
    }


class TestEventHandlerUserRegistered:
    def test_creates_notifications_for_all_channels(
        self,
        handler: EventHandler,
        seed_templates: list[NotificationTemplate],
        db_session: Session,
        mock_celery: MagicMock,
    ) -> None:
        event = _make_user_registered_event()
        handler.handle(event)

        repo = NotificationRepository(db_session)
        event_id = uuid.UUID(event["metadata"]["event_id"])
        channels = repo.get_channels_by_event_id(event_id)

        assert channels == {Channel.EMAIL, Channel.SMS, Channel.PUSH}

    def test_notification_content_rendered(
        self,
        handler: EventHandler,
        seed_templates: list[NotificationTemplate],
        db_session: Session,
    ) -> None:
        event = _make_user_registered_event()
        handler.handle(event)

        event_id = uuid.UUID(event["metadata"]["event_id"])
        repo = NotificationRepository(db_session)
        n = repo.get_by_event_id_and_channel(event_id, Channel.EMAIL)

        assert n is not None
        assert "test@example.com" in n.content["body"]
        assert n.content.get("subject") == "Welcome!"


class TestEventHandlerOrderCompleted:
    def test_creates_notifications_for_all_channels(
        self,
        handler: EventHandler,
        seed_templates: list[NotificationTemplate],
        db_session: Session,
    ) -> None:
        event = _make_order_completed_event()
        handler.handle(event)

        event_id = uuid.UUID(event["metadata"]["event_id"])
        repo = NotificationRepository(db_session)
        channels = repo.get_channels_by_event_id(event_id)
        assert channels == {Channel.EMAIL, Channel.SMS, Channel.PUSH}

    def test_priority_is_high(
        self,
        handler: EventHandler,
        seed_templates: list[NotificationTemplate],
        db_session: Session,
    ) -> None:
        event = _make_order_completed_event()
        handler.handle(event)

        event_id = uuid.UUID(event["metadata"]["event_id"])
        repo = NotificationRepository(db_session)
        n = repo.get_by_event_id_and_channel(event_id, Channel.EMAIL)
        assert n is not None
        assert n.priority == Priority.HIGH


class TestEventHandlerPaymentFailed:
    def test_creates_notifications_for_all_channels(
        self,
        handler: EventHandler,
        seed_templates: list[NotificationTemplate],
        db_session: Session,
    ) -> None:
        event = _make_payment_failed_event()
        handler.handle(event)

        event_id = uuid.UUID(event["metadata"]["event_id"])
        repo = NotificationRepository(db_session)
        channels = repo.get_channels_by_event_id(event_id)
        assert channels == {Channel.EMAIL, Channel.SMS, Channel.PUSH}

    def test_priority_is_critical(
        self,
        handler: EventHandler,
        seed_templates: list[NotificationTemplate],
        db_session: Session,
        mock_celery: MagicMock,
    ) -> None:
        event = _make_payment_failed_event()
        handler.handle(event)

        # Verify Celery tasks dispatched to "critical" queue
        for call in mock_celery.send_task.call_args_list:
            assert call.kwargs["queue"] == Priority.CRITICAL


class TestIdempotency:
    def test_duplicate_event_skipped(
        self,
        handler: EventHandler,
        seed_templates: list[NotificationTemplate],
        db_session: Session,
        mock_celery: MagicMock,
    ) -> None:
        event = _make_user_registered_event()
        handler.handle(event)
        mock_celery.reset_mock()

        # Process same event again
        handler.handle(event)

        # No new Celery tasks dispatched
        mock_celery.send_task.assert_not_called()


class TestUserPreferences:
    def test_disabled_channel_skipped(
        self,
        handler: EventHandler,
        seed_templates: list[NotificationTemplate],
        db_session: Session,
    ) -> None:
        user_id = uuid.uuid4()

        # Create preferences with only email enabled
        pref = UserPreference(
            user_id=user_id,
            channels=[Channel.EMAIL],
            timezone="UTC",
        )
        db_session.add(pref)
        db_session.flush()

        event = _make_user_registered_event(user_id=user_id)
        handler.handle(event)

        event_id = uuid.UUID(event["metadata"]["event_id"])
        repo = NotificationRepository(db_session)
        channels = repo.get_channels_by_event_id(event_id)
        assert channels == {Channel.EMAIL}

    def test_default_preferences_created(
        self,
        handler: EventHandler,
        seed_templates: list[NotificationTemplate],
        db_session: Session,
    ) -> None:
        user_id = uuid.uuid4()
        event = _make_user_registered_event(user_id=user_id)
        handler.handle(event)

        # Default preferences should have been created
        pref = db_session.get(UserPreference, user_id)
        assert pref is not None
        assert set(pref.channels) == {Channel.EMAIL, Channel.SMS, Channel.PUSH}


class TestQuietHours:
    def test_eta_passed_to_celery(
        self,
        handler: EventHandler,
        seed_templates: list[NotificationTemplate],
        db_session: Session,
        mock_celery: MagicMock,
    ) -> None:
        user_id = uuid.uuid4()
        pref = UserPreference(
            user_id=user_id,
            channels=[Channel.EMAIL],
            quiet_hours_start=datetime.time(0, 0),
            quiet_hours_end=datetime.time(23, 59),
            timezone="UTC",
        )
        db_session.add(pref)
        db_session.flush()

        event = _make_user_registered_event(user_id=user_id)
        handler.handle(event)

        call = mock_celery.send_task.call_args
        assert call is not None
        assert "eta" in call.kwargs


class TestCeleryTask:
    def test_correct_task_name_and_queue(
        self,
        handler: EventHandler,
        seed_templates: list[NotificationTemplate],
        db_session: Session,
        mock_celery: MagicMock,
    ) -> None:
        event = _make_user_registered_event()
        handler.handle(event)

        assert mock_celery.send_task.call_count == 3
        for call in mock_celery.send_task.call_args_list:
            assert call.args[0] == "delivery_worker.tasks.send_notification"
            assert "notification_id" in call.kwargs["kwargs"]
            assert call.kwargs["queue"] == Priority.NORMAL


class TestStatusPublish:
    def test_status_published_for_each_notification(
        self,
        handler: EventHandler,
        seed_templates: list[NotificationTemplate],
        db_session: Session,
        mock_status_producer: MagicMock,
    ) -> None:
        event = _make_user_registered_event()
        handler.handle(event)

        assert mock_status_producer.publish_status.call_count == 3
        for call in mock_status_producer.publish_status.call_args_list:
            assert call.kwargs["status"] == NotificationStatus.PENDING
            assert call.kwargs["event_type"] == "user.registered"


class TestMissingTemplate:
    def test_channel_skipped_when_no_template(
        self,
        handler: EventHandler,
        db_session: Session,
        mock_celery: MagicMock,
    ) -> None:
        """No templates seeded → no notifications created."""
        event = _make_user_registered_event()
        handler.handle(event)

        mock_celery.send_task.assert_not_called()
