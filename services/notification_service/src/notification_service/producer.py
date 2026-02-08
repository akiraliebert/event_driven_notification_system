"""Kafka producer for notification delivery status events."""

import json
import logging
from uuid import UUID

from confluent_kafka import Producer

from shared.config import KafkaConfig

logger = logging.getLogger(__name__)


class KafkaStatusProducer:
    """Publishes notification status events to the notification.delivery topic."""

    def __init__(self, config: KafkaConfig) -> None:
        self._topic = config.delivery_events_topic
        self._producer = Producer({
            "bootstrap.servers": config.bootstrap_servers,
            "acks": "all",
            "enable.idempotence": True,
            "linger.ms": 5,
            "compression.type": "lz4",
        })

    def publish_status(
        self,
        notification_id: UUID,
        status: str,
        event_type: str,
        channel: str,
        user_id: UUID,
    ) -> None:
        """Publish a notification status event."""
        value = json.dumps({
            "notification_id": str(notification_id),
            "status": status,
            "event_type": event_type,
            "channel": channel,
            "user_id": str(user_id),
        }).encode("utf-8")

        self._producer.produce(
            topic=self._topic,
            key=str(notification_id).encode("utf-8"),
            value=value,
            on_delivery=self._on_delivery,
        )
        self._producer.poll(0)

    def flush(self, timeout: float = 10.0) -> int:
        """Flush remaining messages. Returns number of unflushed messages."""
        return self._producer.flush(timeout=timeout)

    def close(self) -> None:
        """Flush remaining messages before shutdown."""
        remaining = self.flush()
        if remaining > 0:
            logger.warning(
                "Producer closed with unflushed messages",
                extra={"remaining": remaining},
            )

    @staticmethod
    def _on_delivery(err: object, msg: object) -> None:
        if err is not None:
            logger.error("Kafka delivery failed: %s", err)
