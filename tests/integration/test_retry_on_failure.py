"""Retry-on-failure integration tests.

Verifies that delivery attempts are tracked and that the status
transitions correctly when a provider fails.
"""

import uuid
from unittest.mock import MagicMock

import httpx
import pytest
from sqlalchemy.orm import Session, sessionmaker

from shared.db.models import Notification
from shared.enums import NotificationStatus

from delivery_worker.celery import app as delivery_app
from delivery_worker.providers.base import DeliveryResult
from delivery_worker.tasks import send_notification
from tests.integration.helpers import poll_notifications

pytestmark = pytest.mark.integration


class TestProviderFailure:
    def test_failure_increments_attempts(
        self,
        http_client: httpx.Client,
        notification_consumer: None,
        session_factory: sessionmaker[Session],
        _setup_delivery_worker: None,
    ) -> None:
        """When provider returns failure, attempts is incremented."""
        user_id = str(uuid.uuid4())
        resp = http_client.post("/events", json={
            "event_type": "user.registered",
            "payload": {"user_id": user_id, "email": "retry@test.com"},
        })
        assert resp.status_code == 202
        event_id = resp.json()["event_id"]

        notifications = poll_notifications(session_factory, event_id, expected=3)
        email_notif = next(n for n in notifications if n.channel == "email")

        # Patch provider to fail
        original_registry = delivery_app.conf._provider_registry
        failing_provider = MagicMock()
        failing_provider.send.return_value = DeliveryResult(
            success=False, details="Simulated timeout",
        )

        original_get = original_registry.get

        def _patched_get(channel: str):  # noqa: ANN202
            if channel == "email":
                return failing_provider
            return original_get(channel)

        original_registry.get = _patched_get
        try:
            send_notification(str(email_notif.id))
        finally:
            original_registry.get = original_get

        with session_factory() as session:
            n = session.get(Notification, email_notif.id)
            assert n is not None
            assert n.attempts == 1
            assert n.status == NotificationStatus.PENDING  # retryable


class TestExhaustedRetries:
    def test_status_becomes_failed(
        self,
        http_client: httpx.Client,
        notification_consumer: None,
        session_factory: sessionmaker[Session],
        _setup_delivery_worker: None,
    ) -> None:
        """When all attempts exhausted, status becomes FAILED."""
        user_id = str(uuid.uuid4())
        resp = http_client.post("/events", json={
            "event_type": "user.registered",
            "payload": {"user_id": user_id, "email": "exhaust@test.com"},
        })
        assert resp.status_code == 202
        event_id = resp.json()["event_id"]

        notifications = poll_notifications(session_factory, event_id, expected=3)
        email_notif = next(n for n in notifications if n.channel == "email")

        # Set attempts to max_attempts - 1 so next failure is the last
        with session_factory() as session:
            n = session.get(Notification, email_notif.id)
            assert n is not None
            n.attempts = n.max_attempts - 1
            session.commit()

        # Patch provider to fail
        original_registry = delivery_app.conf._provider_registry
        failing_provider = MagicMock()
        failing_provider.send.return_value = DeliveryResult(
            success=False, details="Final failure",
        )

        original_get = original_registry.get

        def _patched_get(channel: str):  # noqa: ANN202
            if channel == "email":
                return failing_provider
            return original_get(channel)

        original_registry.get = _patched_get
        try:
            send_notification(str(email_notif.id))
        finally:
            original_registry.get = original_get

        with session_factory() as session:
            n = session.get(Notification, email_notif.id)
            assert n is not None
            assert n.status == NotificationStatus.FAILED
            assert n.failed_reason == "Final failure"
