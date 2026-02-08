import logging
from uuid import UUID

from confluent_kafka import KafkaException, Producer

from shared.config import KafkaConfig
from shared.events.typed import AnyTypedEvent

logger = logging.getLogger(__name__)


class KafkaEventProducer:
    """Wraps confluent_kafka.Producer for publishing typed events to Kafka."""

    def __init__(self, config: KafkaConfig) -> None:
        self._topic = config.domain_events_topic
        self._producer = Producer({
            "bootstrap.servers": config.bootstrap_servers,
            "acks": "all",
            "enable.idempotence": True,
            "linger.ms": 5,
            "compression.type": "lz4",
        })

    def publish_event(self, event: AnyTypedEvent, partition_key: UUID) -> None:
        """Serialize and publish a typed event to the domain.events topic.

        Raises KafkaException or BufferError on failure.
        """
        value = event.model_dump_json().encode("utf-8")
        key = str(partition_key).encode("utf-8")

        self._producer.produce(
            topic=self._topic,
            key=key,
            value=value,
            on_delivery=self._on_delivery,
        )
        self._producer.poll(0)

    def health_check(self) -> bool:
        """Check Kafka connectivity via list_topics."""
        try:
            metadata = self._producer.list_topics(timeout=5.0)
            return len(metadata.brokers) > 0
        except KafkaException:
            return False

    def close(self) -> None:
        """Flush remaining messages before shutdown."""
        remaining = self._producer.flush(timeout=10.0)
        if remaining > 0:
            logger.warning(
                "Producer closed with unflushed messages",
                extra={"remaining": remaining},
            )

    @staticmethod
    def _on_delivery(err: object, msg: object) -> None:
        if err is not None:
            logger.error("Kafka delivery failed: %s", err)
