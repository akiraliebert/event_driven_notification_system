"""Priority assignment integration tests.

Verifies that each event type produces notifications with the correct
priority level as defined in the priority mapping.
"""

import uuid

import httpx
import pytest
from sqlalchemy.orm import Session, sessionmaker

from tests.integration.helpers import poll_notifications, poll_notifications_by_user

pytestmark = pytest.mark.integration


class TestPriorityAssignment:
    def test_all_event_types_have_correct_priority(
        self,
        http_client: httpx.Client,
        notification_consumer: None,
        session_factory: sessionmaker[Session],
    ) -> None:
        """Each event type maps to the expected priority level."""
        user_id = str(uuid.uuid4())

        events = [
            {
                "event_type": "user.registered",
                "payload": {"user_id": user_id, "email": "prio@test.com"},
            },
            {
                "event_type": "order.completed",
                "payload": {
                    "user_id": user_id,
                    "order_id": str(uuid.uuid4()),
                    "total_amount": "50.00",
                },
            },
            {
                "event_type": "payment.failed",
                "payload": {
                    "user_id": user_id,
                    "payment_id": str(uuid.uuid4()),
                    "reason": "NSF",
                },
            },
        ]

        event_ids = []
        for ev in events:
            resp = http_client.post("/events", json=ev)
            assert resp.status_code == 202
            event_ids.append(resp.json()["event_id"])

        # Wait for all 9 notifications (3 events × 3 channels)
        all_notifs = poll_notifications_by_user(
            session_factory, user_id, expected=9, timeout=15.0,
        )
        assert len(all_notifs) == 9

        expected_priorities = {
            "user.registered": "normal",
            "order.completed": "high",
            "payment.failed": "critical",
        }

        for n in all_notifs:
            expected = expected_priorities[n.source_event_type]
            assert n.priority == expected, (
                f"Notification for {n.source_event_type}/{n.channel}: "
                f"expected priority={expected}, got={n.priority}"
            )

    def test_celery_queue_matches_priority(
        self,
        http_client: httpx.Client,
        notification_consumer: None,
        session_factory: sessionmaker[Session],
    ) -> None:
        """Celery tasks are dispatched to the queue matching the priority."""
        user_id = str(uuid.uuid4())
        resp = http_client.post("/events", json={
            "event_type": "payment.failed",
            "payload": {
                "user_id": user_id,
                "payment_id": str(uuid.uuid4()),
                "reason": "Card declined",
            },
        })
        assert resp.status_code == 202
        event_id = resp.json()["event_id"]

        notifications = poll_notifications(session_factory, event_id, expected=3)
        for n in notifications:
            assert n.priority == "critical"
