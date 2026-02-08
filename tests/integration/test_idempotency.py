"""Idempotency integration test.

Publishes the same event (same event_id) to Kafka twice and verifies
that only one set of notifications is created.
"""

import json
import time
import uuid
from datetime import datetime, timezone

import pytest
from confluent_kafka import Producer
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from shared.db.models import Notification

pytestmark = pytest.mark.integration


class TestKafkaMessageIdempotency:
    def test_duplicate_message_creates_no_extra_notifications(
        self,
        notification_consumer: None,
        session_factory: sessionmaker[Session],
        kafka_bootstrap: str,
        kafka_topics: list[str],
    ) -> None:
        """Same Kafka message consumed twice → exactly 3 notifications."""
        user_id = str(uuid.uuid4())
        event_id = str(uuid.uuid4())
        raw_event = {
            "metadata": {
                "event_id": event_id,
                "event_type": "user.registered",
                "occurred_at": datetime.now(timezone.utc).isoformat(),
                "version": 1,
            },
            "payload": {
                "user_id": user_id,
                "email": "idempotent@test.com",
            },
        }

        producer = Producer({"bootstrap.servers": kafka_bootstrap})
        encoded = json.dumps(raw_event).encode("utf-8")
        key = user_id.encode("utf-8")

        for _ in range(2):
            producer.produce("domain.events", key=key, value=encoded)
        producer.flush(timeout=5)

        # Wait for consumer to process both messages
        event_uuid = uuid.UUID(event_id)
        deadline = time.monotonic() + 10.0
        max_seen = 0

        while time.monotonic() < deadline:
            with session_factory() as session:
                stmt = select(Notification).where(
                    Notification.source_event_id == event_uuid,
                )
                count = len(list(session.scalars(stmt).all()))
                max_seen = max(max_seen, count)
                if count >= 3:
                    break
            time.sleep(0.3)

        # Give a bit more time to catch any extra duplicates
        time.sleep(1.0)

        with session_factory() as session:
            stmt = select(Notification).where(
                Notification.source_event_id == event_uuid,
            )
            notifications = list(session.scalars(stmt).all())

        assert len(notifications) == 3
        channels = {n.channel for n in notifications}
        assert channels == {"email", "sms", "push"}
