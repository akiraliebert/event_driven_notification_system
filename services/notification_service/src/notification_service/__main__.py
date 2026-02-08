"""Entry point for the Notification Service.

Runs a Kafka consumer loop that processes domain events and creates
notification delivery tasks via Celery.
"""

import json
import logging
import signal
import sys
from collections import defaultdict

from celery import Celery

from shared.config import KafkaConfig, PostgresConfig
from shared.db.base import create_db_engine, create_session_factory

from notification_service.config import CeleryConfig, NotificationServiceConfig
from notification_service.consumer import KafkaEventConsumer
from notification_service.handler import EventHandler
from notification_service.log import setup_logging
from notification_service.producer import KafkaStatusProducer

logger = logging.getLogger(__name__)

MAX_HANDLER_RETRIES = 3


def main() -> None:
    service_config = NotificationServiceConfig()
    setup_logging(service_config.log_level)

    kafka_config = KafkaConfig()
    postgres_config = PostgresConfig()
    celery_config = CeleryConfig()

    # Database
    engine = create_db_engine(postgres_config.dsn, pool_pre_ping=True)
    session_factory = create_session_factory(engine)

    # Celery (used only for send_task, no worker here)
    celery_app = Celery(broker=celery_config.broker_url)

    # Kafka
    consumer = KafkaEventConsumer(kafka_config, service_config.kafka_group_id)
    status_producer = KafkaStatusProducer(kafka_config)

    # Handler
    handler = EventHandler(session_factory, celery_app, status_producer)

    # Graceful shutdown
    running = True

    # Track handler failures per (topic, partition, offset) to detect poison pills
    failure_counts: defaultdict[tuple[str, int, int], int] = defaultdict(int)

    def _shutdown(signum: int, _frame: object) -> None:
        nonlocal running
        sig_name = signal.Signals(signum).name
        logger.info("Received %s, shutting down...", sig_name)
        running = False

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    logger.info("Notification Service started")

    try:
        while running:
            msg = consumer.poll(timeout=1.0)
            if msg is None:
                continue

            try:
                raw_event = json.loads(msg.value().decode("utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError):
                logger.error(
                    "Malformed message, skipping",
                    extra={
                        "topic": msg.topic(),
                        "partition": msg.partition(),
                        "offset": msg.offset(),
                    },
                )
                consumer.commit(msg)
                continue

            try:
                handler.handle(raw_event)
            except ValueError:
                logger.exception(
                    "Invalid event, skipping",
                    extra={"raw_event": raw_event},
                )
                consumer.commit(msg)
                continue
            except Exception:
                msg_key = (msg.topic(), msg.partition(), msg.offset())
                failure_counts[msg_key] += 1
                if failure_counts[msg_key] >= MAX_HANDLER_RETRIES:
                    logger.error(
                        "Poison pill detected: message failed %d times, "
                        "committing offset to skip",
                        MAX_HANDLER_RETRIES,
                        extra={
                            "topic": msg.topic(),
                            "partition": msg.partition(),
                            "offset": msg.offset(),
                            "raw_event": raw_event,
                        },
                    )
                    del failure_counts[msg_key]
                    consumer.commit(msg)
                else:
                    logger.exception(
                        "Failed to process event (attempt %d/%d), "
                        "will retry on redelivery",
                        failure_counts[msg_key],
                        MAX_HANDLER_RETRIES,
                        extra={"raw_event": raw_event},
                    )
                continue

            consumer.commit(msg)
    finally:
        status_producer.close()
        consumer.close()
        engine.dispose()
        logger.info("Notification Service stopped")


if __name__ == "__main__":
    main()
