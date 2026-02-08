"""Kafka consumer wrapper for domain events."""

import logging

from confluent_kafka import Consumer, KafkaError, KafkaException, Message

from shared.config import KafkaConfig

logger = logging.getLogger(__name__)


class KafkaEventConsumer:
    """Wraps confluent_kafka.Consumer for consuming domain events."""

    def __init__(self, config: KafkaConfig, group_id: str) -> None:
        self._topic = config.domain_events_topic
        self._consumer = Consumer({
            "bootstrap.servers": config.bootstrap_servers,
            "group.id": group_id,
            "auto.offset.reset": "earliest",
            "enable.auto.commit": False,
        })
        self._consumer.subscribe([self._topic])
        logger.info(
            "Subscribed to topic",
            extra={"topic": self._topic, "group_id": group_id},
        )

    def poll(self, timeout: float = 1.0) -> Message | None:
        """Poll for a single message. Returns None on timeout or partition EOF."""
        msg = self._consumer.poll(timeout)
        if msg is None:
            return None

        err = msg.error()
        if err is not None:
            if err.code() == KafkaError._PARTITION_EOF:
                return None
            raise KafkaException(err)

        return msg

    def commit(self, message: Message) -> None:
        """Synchronously commit the offset for the given message."""
        self._consumer.commit(message=message, asynchronous=False)

    def close(self) -> None:
        """Close the consumer, leaving the consumer group."""
        self._consumer.close()
        logger.info("Consumer closed")
