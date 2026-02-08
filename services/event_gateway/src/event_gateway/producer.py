import logging
from uuid import UUID

from confluent_kafka import KafkaError, KafkaException, Message, Producer

from shared.config import KafkaConfig
from shared.events.typed import AnyTypedEvent

logger = logging.getLogger(__name__)

_FLUSH_TIMEOUT_SECONDS = 5.0


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

        Blocks until the broker acknowledges the message so that a 202
        response genuinely means "accepted by broker".

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
        remaining = self._producer.flush(timeout=_FLUSH_TIMEOUT_SECONDS)
        if remaining > 0:
            raise KafkaException(
                KafkaError._TIMED_OUT,
                "Timed out waiting for broker acknowledgement",
            )

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
    def _on_delivery(err: KafkaError | None, msg: Message) -> None:
        if err is not None:
            logger.error("Kafka delivery failed: %s", err)
