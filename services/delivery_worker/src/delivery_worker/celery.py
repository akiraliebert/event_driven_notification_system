"""Celery application setup and worker initialization."""

import logging

from celery import Celery, signals
from kombu import Queue
from redis import Redis

from shared.config import KafkaConfig, PostgresConfig, RedisConfig
from shared.db.base import create_db_engine, create_session_factory

from delivery_worker.config import CeleryConfig, DeliveryConfig, RateLimitConfig
from delivery_worker.log import setup_logging
from delivery_worker.providers import create_default_registry
from delivery_worker.rate_limiter import RateLimiter
from delivery_worker.status_publisher import KafkaStatusPublisher

logger = logging.getLogger(__name__)

celery_config = CeleryConfig()

app = Celery("delivery_worker", broker=celery_config.broker_url)

app.conf.update(
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_queues=[
        Queue("critical"),
        Queue("high"),
        Queue("normal"),
        Queue("low"),
    ],
    task_default_queue="normal",
)

app.autodiscover_tasks(["delivery_worker"])


@signals.worker_init.connect
def _init_worker(**_kwargs: object) -> None:
    """Initialize shared resources once per worker process."""
    delivery_config = DeliveryConfig()
    setup_logging(delivery_config.log_level)

    pg_config = PostgresConfig()
    engine = create_db_engine(pg_config.dsn)
    session_factory = create_session_factory(engine)

    redis_config = RedisConfig()
    redis_client = Redis(
        host=redis_config.host,
        port=redis_config.port,
        db=redis_config.db,
    )

    rate_limit_config = RateLimitConfig()
    rate_limiter = RateLimiter(redis_client, rate_limit_config)

    kafka_config = KafkaConfig()
    status_publisher = KafkaStatusPublisher(kafka_config)

    provider_registry = create_default_registry()

    app.conf.update(
        _session_factory=session_factory,
        _provider_registry=provider_registry,
        _rate_limiter=rate_limiter,
        _status_publisher=status_publisher,
        _delivery_config=delivery_config,
    )
    logger.info("Worker initialized")


@signals.worker_shutdown.connect
def _shutdown_worker(**_kwargs: object) -> None:
    """Clean up resources on worker shutdown."""
    publisher: KafkaStatusPublisher | None = getattr(
        app.conf, "_status_publisher", None
    )
    if publisher is not None:
        publisher.close()
    logger.info("Worker shut down")
