"""Full flow integration tests: HTTP → Kafka → DB → Delivery → DELIVERED.

Each test sends one event type through the entire pipeline and verifies
that notifications are created and delivered for all enabled channels.
"""

import uuid

import httpx
import pytest
from sqlalchemy.orm import Session, sessionmaker

from shared.enums import NotificationStatus

from tests.integration.helpers import poll_notifications

pytestmark = pytest.mark.integration


def _deliver_all(notifications: list) -> None:
    """Invoke delivery_worker.tasks.send_notification for each notification."""
    from delivery_worker.tasks import send_notification

    for n in notifications:
        send_notification(str(n.id))


class TestUserRegisteredFlow:
    def test_creates_and_delivers_three_channels(
        self,
        http_client: httpx.Client,
        notification_consumer: None,
        session_factory: sessionmaker[Session],
        _setup_delivery_worker: None,
    ) -> None:
        user_id = str(uuid.uuid4())
        resp = http_client.post("/events", json={
            "event_type": "user.registered",
            "payload": {"user_id": user_id, "email": "alice@example.com"},
        })
        assert resp.status_code == 202
        event_id = resp.json()["event_id"]

        notifications = poll_notifications(session_factory, event_id, expected=3)
        assert len(notifications) == 3

        channels = {n.channel for n in notifications}
        assert channels == {"email", "sms", "push"}
        for n in notifications:
            assert n.status == NotificationStatus.PENDING
            assert n.priority == "normal"

        _deliver_all(notifications)

        with session_factory() as session:
            for n in notifications:
                refreshed = session.get(type(n), n.id)
                assert refreshed is not None
                assert refreshed.status == NotificationStatus.DELIVERED
                assert refreshed.delivered_at is not None


class TestOrderCompletedFlow:
    def test_creates_and_delivers_with_high_priority(
        self,
        http_client: httpx.Client,
        notification_consumer: None,
        session_factory: sessionmaker[Session],
        _setup_delivery_worker: None,
    ) -> None:
        user_id = str(uuid.uuid4())
        resp = http_client.post("/events", json={
            "event_type": "order.completed",
            "payload": {
                "user_id": user_id,
                "order_id": str(uuid.uuid4()),
                "total_amount": "149.99",
            },
        })
        assert resp.status_code == 202
        event_id = resp.json()["event_id"]

        notifications = poll_notifications(session_factory, event_id, expected=3)
        assert len(notifications) == 3

        for n in notifications:
            assert n.priority == "high"

        _deliver_all(notifications)

        with session_factory() as session:
            for n in notifications:
                refreshed = session.get(type(n), n.id)
                assert refreshed is not None
                assert refreshed.status == NotificationStatus.DELIVERED


class TestPaymentFailedFlow:
    def test_creates_and_delivers_with_critical_priority(
        self,
        http_client: httpx.Client,
        notification_consumer: None,
        session_factory: sessionmaker[Session],
        _setup_delivery_worker: None,
    ) -> None:
        user_id = str(uuid.uuid4())
        resp = http_client.post("/events", json={
            "event_type": "payment.failed",
            "payload": {
                "user_id": user_id,
                "payment_id": str(uuid.uuid4()),
                "reason": "Insufficient funds",
            },
        })
        assert resp.status_code == 202
        event_id = resp.json()["event_id"]

        notifications = poll_notifications(session_factory, event_id, expected=3)
        assert len(notifications) == 3

        for n in notifications:
            assert n.priority == "critical"

        _deliver_all(notifications)

        with session_factory() as session:
            for n in notifications:
                refreshed = session.get(type(n), n.id)
                assert refreshed is not None
                assert refreshed.status == NotificationStatus.DELIVERED
