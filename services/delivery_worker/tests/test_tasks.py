"""Tests for the send_notification Celery task."""

import uuid
from collections.abc import Generator
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.orm import Session

from shared.db.models import Notification
from shared.enums import Channel, NotificationStatus

from delivery_worker.config import DeliveryConfig
from delivery_worker.providers.base import DeliveryResult
from delivery_worker.tasks import _get_backoff, send_notification


@pytest.fixture(autouse=True)
def mock_celery_app(
    session_factory: MagicMock,
    mock_provider_registry: MagicMock,
    mock_rate_limiter: MagicMock,
    mock_status_publisher: MagicMock,
    delivery_config: DeliveryConfig,
) -> Generator[MagicMock, None, None]:
    """Inject test dependencies into the Celery app conf."""
    with patch("delivery_worker.tasks.app") as mock_app:
        mock_app.conf._session_factory = session_factory
        mock_app.conf._provider_registry = mock_provider_registry
        mock_app.conf._rate_limiter = mock_rate_limiter
        mock_app.conf._status_publisher = mock_status_publisher
        mock_app.conf._delivery_config = delivery_config
        mock_app.send_task = MagicMock()
        yield mock_app


class TestSendNotificationSuccess:
    def test_successful_delivery_sets_delivered_status(
        self,
        db_session: Session,
        sample_notification: Notification,
    ) -> None:
        send_notification(str(sample_notification.id))

        db_session.refresh(sample_notification)
        assert sample_notification.status == NotificationStatus.DELIVERED
        assert sample_notification.delivered_at is not None

    def test_successful_delivery_publishes_status(
        self,
        mock_status_publisher: MagicMock,
        sample_notification: Notification,
    ) -> None:
        send_notification(str(sample_notification.id))

        mock_status_publisher.publish_status.assert_called_once()
        call_kwargs = mock_status_publisher.publish_status.call_args.kwargs
        assert call_kwargs["status"] == NotificationStatus.DELIVERED
        assert call_kwargs["notification_id"] == sample_notification.id

    def test_correct_provider_called_for_channel(
        self,
        mock_provider_registry: MagicMock,
        sample_notification: Notification,
    ) -> None:
        send_notification(str(sample_notification.id))

        mock_provider_registry.get.assert_called_once_with(Channel.EMAIL)


class TestSendNotificationFailure:
    def test_failed_delivery_increments_attempts_and_requeues(
        self,
        db_session: Session,
        mock_provider_registry: MagicMock,
        mock_celery_app: MagicMock,
        sample_notification: Notification,
    ) -> None:
        provider = mock_provider_registry.get.return_value
        provider.send.return_value = DeliveryResult(
            success=False, details="Connection refused"
        )

        send_notification(str(sample_notification.id))

        mock_celery_app.send_task.assert_called_once()
        call_kwargs = mock_celery_app.send_task.call_args.kwargs
        assert call_kwargs["countdown"] == 60  # first backoff

        db_session.refresh(sample_notification)
        assert sample_notification.attempts == 1
        assert sample_notification.status == NotificationStatus.PENDING

    def test_provider_exception_treated_as_failure(
        self,
        db_session: Session,
        mock_provider_registry: MagicMock,
        sample_notification: Notification,
    ) -> None:
        provider = mock_provider_registry.get.return_value
        provider.send.side_effect = RuntimeError("boom")

        send_notification(str(sample_notification.id))

        db_session.refresh(sample_notification)
        assert sample_notification.attempts == 1
        assert sample_notification.status == NotificationStatus.PENDING


class TestSendNotificationExhaustedRetries:
    def test_max_attempts_reached_sets_failed_status(
        self,
        db_session: Session,
        mock_provider_registry: MagicMock,
        mock_status_publisher: MagicMock,
        sample_notification: Notification,
    ) -> None:
        sample_notification.attempts = 2
        db_session.flush()

        provider = mock_provider_registry.get.return_value
        provider.send.return_value = DeliveryResult(
            success=False, details="Timeout"
        )

        send_notification(str(sample_notification.id))

        db_session.refresh(sample_notification)
        assert sample_notification.status == NotificationStatus.FAILED
        assert sample_notification.failed_reason == "Timeout"
        assert sample_notification.attempts == 3

        mock_status_publisher.publish_status.assert_called_once()
        call_kwargs = mock_status_publisher.publish_status.call_args.kwargs
        assert call_kwargs["status"] == NotificationStatus.FAILED


class TestSendNotificationRateLimit:
    def test_rate_limited_reschedules_task(
        self,
        db_session: Session,
        mock_rate_limiter: MagicMock,
        mock_provider_registry: MagicMock,
        mock_celery_app: MagicMock,
        sample_notification: Notification,
    ) -> None:
        mock_rate_limiter.acquire.return_value = False

        send_notification(str(sample_notification.id))

        db_session.refresh(sample_notification)
        assert sample_notification.status == NotificationStatus.PENDING
        # Provider should not have been called
        provider = mock_provider_registry.get.return_value
        provider.send.assert_not_called()
        # Task re-queued with delay
        mock_celery_app.send_task.assert_called_once()


class TestSendNotificationIdempotency:
    def test_already_delivered_is_skipped(
        self,
        db_session: Session,
        mock_provider_registry: MagicMock,
        sample_notification: Notification,
    ) -> None:
        sample_notification.status = NotificationStatus.DELIVERED
        sample_notification.delivered_at = datetime.now(timezone.utc)
        db_session.flush()

        send_notification(str(sample_notification.id))

        provider = mock_provider_registry.get.return_value
        provider.send.assert_not_called()

    def test_permanently_failed_is_skipped(
        self,
        db_session: Session,
        mock_provider_registry: MagicMock,
        sample_notification: Notification,
    ) -> None:
        sample_notification.status = NotificationStatus.FAILED
        sample_notification.attempts = 3
        sample_notification.max_attempts = 3
        db_session.flush()

        send_notification(str(sample_notification.id))

        provider = mock_provider_registry.get.return_value
        provider.send.assert_not_called()


class TestSendNotificationNotFound:
    def test_missing_notification_does_not_raise(self) -> None:
        send_notification(str(uuid.uuid4()))


class TestGetBackoff:
    def test_first_attempt_backoff(self) -> None:
        assert _get_backoff(1, [60, 300, 900]) == 60

    def test_second_attempt_backoff(self) -> None:
        assert _get_backoff(2, [60, 300, 900]) == 300

    def test_third_attempt_backoff(self) -> None:
        assert _get_backoff(3, [60, 300, 900]) == 900

    def test_beyond_schedule_uses_last_value(self) -> None:
        assert _get_backoff(5, [60, 300, 900]) == 900
