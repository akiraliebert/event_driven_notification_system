"""Integration test fixtures using testcontainers.

Session-scoped containers for Kafka, PostgreSQL, Redis.
Function-scoped DB cleanup and service orchestration.
"""

import json
import os
import threading
import uuid
from collections.abc import Generator
from pathlib import Path
from typing import Any

import httpx
import pytest
from celery import Celery
from confluent_kafka import Consumer as KafkaRawConsumer
from confluent_kafka import KafkaError
from confluent_kafka.admin import AdminClient, NewTopic
from redis import Redis
from sqlalchemy import text
from sqlalchemy.orm import Session, sessionmaker
from testcontainers.kafka import KafkaContainer
from testcontainers.postgres import PostgresContainer
from testcontainers.redis import RedisContainer
from werkzeug.serving import make_server

from shared.config import KafkaConfig
from shared.db.base import Base, create_db_engine, create_session_factory
from shared.db.models import Notification, UserPreference

pytestmark = pytest.mark.integration

# ---------------------------------------------------------------------------
# Containers (session-scoped)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def postgres_container() -> Generator[PostgresContainer, None, None]:
    with PostgresContainer("postgres:16-alpine", driver="psycopg2") as pg:
        yield pg


@pytest.fixture(scope="session")
def kafka_container() -> Generator[KafkaContainer, None, None]:
    with KafkaContainer("confluentinc/cp-kafka:7.7.1") as kafka:
        yield kafka


@pytest.fixture(scope="session")
def redis_container() -> Generator[RedisContainer, None, None]:
    with RedisContainer("redis:7-alpine") as redis_c:
        yield redis_c


# ---------------------------------------------------------------------------
# Derived connection parameters (session-scoped)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def pg_dsn(postgres_container: PostgresContainer) -> str:
    return postgres_container.get_connection_url()


@pytest.fixture(scope="session")
def kafka_bootstrap(kafka_container: KafkaContainer) -> str:
    return kafka_container.get_bootstrap_server()


@pytest.fixture(scope="session")
def redis_host_port(redis_container: RedisContainer) -> tuple[str, int]:
    host = redis_container.get_container_host_ip()
    port = int(redis_container.get_exposed_port(6379))
    return host, port


@pytest.fixture(scope="session")
def redis_url(redis_host_port: tuple[str, int]) -> str:
    host, port = redis_host_port
    return f"redis://{host}:{port}/0"


# ---------------------------------------------------------------------------
# Environment variables (session-scoped, autouse)
# Pydantic-settings configs read these automatically.
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session", autouse=True)
def _set_env_vars(
    pg_dsn: str,
    kafka_bootstrap: str,
    redis_host_port: tuple[str, int],
    redis_url: str,
) -> Generator[None, None, None]:
    from urllib.parse import urlparse

    parsed = urlparse(pg_dsn)
    overrides = {
        "POSTGRES_HOST": parsed.hostname or "localhost",
        "POSTGRES_PORT": str(parsed.port or 5432),
        "POSTGRES_DATABASE": (parsed.path or "/test").lstrip("/"),
        "POSTGRES_USER": parsed.username or "test",
        "POSTGRES_PASSWORD": parsed.password or "test",
        "KAFKA_BOOTSTRAP_SERVERS": kafka_bootstrap,
        "REDIS_HOST": redis_host_port[0],
        "REDIS_PORT": str(redis_host_port[1]),
        "CELERY_BROKER_URL": redis_url,
    }

    saved: dict[str, str | None] = {}
    for key, value in overrides.items():
        saved[key] = os.environ.get(key)
        os.environ[key] = value

    yield

    for key, old in saved.items():
        if old is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = old


# ---------------------------------------------------------------------------
# Database (session-scoped)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def db_engine(pg_dsn: str, _set_env_vars: None):  # noqa: ANN201
    """Create engine and run Alembic migrations against testcontainer PG."""
    from alembic import command
    from alembic.config import Config as AlembicConfig

    engine = create_db_engine(pg_dsn, pool_pre_ping=True)

    shared_dir = Path(__file__).resolve().parents[2] / "shared"
    alembic_cfg = AlembicConfig(str(shared_dir / "alembic.ini"))
    alembic_cfg.set_main_option("script_location", str(shared_dir / "alembic"))
    alembic_cfg.set_main_option("sqlalchemy.url", pg_dsn)
    command.upgrade(alembic_cfg, "head")

    yield engine
    engine.dispose()


@pytest.fixture(scope="session")
def session_factory(db_engine) -> sessionmaker[Session]:  # noqa: ANN001
    return create_session_factory(db_engine)


@pytest.fixture(autouse=True)
def _cleanup_db(session_factory: sessionmaker[Session]) -> Generator[None, None, None]:
    """Truncate notification-related tables after each test."""
    yield
    with session_factory() as session:
        session.execute(text("TRUNCATE notifications, user_preferences CASCADE"))
        session.commit()


# ---------------------------------------------------------------------------
# Kafka topics (session-scoped)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def kafka_topics(kafka_bootstrap: str) -> list[str]:
    admin = AdminClient({"bootstrap.servers": kafka_bootstrap})
    topics = [
        NewTopic("domain.events", num_partitions=3, replication_factor=1),
        NewTopic("notification.delivery", num_partitions=3, replication_factor=1),
    ]
    futures = admin.create_topics(topics)
    for _topic, future in futures.items():
        future.result(timeout=30)
    return ["domain.events", "notification.delivery"]


# ---------------------------------------------------------------------------
# Delivery worker setup (session-scoped)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def _setup_delivery_worker(
    session_factory: sessionmaker[Session],
    redis_host_port: tuple[str, int],
    kafka_bootstrap: str,
    kafka_topics: list[str],
) -> Generator[None, None, None]:
    """Patch delivery_worker.celery.app.conf with test resources.

    This allows calling send_notification() directly in tests
    without running a real Celery worker process.
    """
    from delivery_worker.celery import app as delivery_app
    from delivery_worker.config import DeliveryConfig, RateLimitConfig
    from delivery_worker.providers import create_default_registry
    from delivery_worker.rate_limiter import RateLimiter
    from delivery_worker.status_publisher import KafkaStatusPublisher

    redis_client = Redis(host=redis_host_port[0], port=redis_host_port[1])
    rate_limiter = RateLimiter(redis_client, RateLimitConfig())
    kafka_config = KafkaConfig()
    status_publisher = KafkaStatusPublisher(kafka_config)
    provider_registry = create_default_registry()

    delivery_app.conf.update(
        _session_factory=session_factory,
        _provider_registry=provider_registry,
        _rate_limiter=rate_limiter,
        _status_publisher=status_publisher,
        _delivery_config=DeliveryConfig(),
    )

    yield

    status_publisher.close()
    redis_client.close()


# ---------------------------------------------------------------------------
# Event Gateway (function-scoped)
# ---------------------------------------------------------------------------


@pytest.fixture()
def gateway_url(
    kafka_bootstrap: str,
    kafka_topics: list[str],
) -> Generator[str, None, None]:
    """Start Flask event-gateway in a background thread, yield base URL."""
    from event_gateway.app import create_app
    from event_gateway.producer import KafkaEventProducer

    kafka_config = KafkaConfig()
    producer = KafkaEventProducer(kafka_config)
    app = create_app(producer)
    app.config["TESTING"] = True

    server = make_server("127.0.0.1", 0, app)
    port = server.server_address[1]

    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    yield f"http://127.0.0.1:{port}"

    server.shutdown()
    producer.close()


@pytest.fixture()
def http_client(gateway_url: str) -> Generator[httpx.Client, None, None]:
    with httpx.Client(base_url=gateway_url, timeout=10.0) as client:
        yield client


# ---------------------------------------------------------------------------
# Notification Service consumer (function-scoped)
# ---------------------------------------------------------------------------


@pytest.fixture()
def notification_consumer(
    session_factory: sessionmaker[Session],
    kafka_topics: list[str],
    redis_url: str,
) -> Generator[None, None, None]:
    """Run the notification service consumer loop in a background thread.

    Uses a unique Kafka group_id per test to avoid stale offsets.
    Celery send_task goes to Redis but no worker picks it up —
    delivery is invoked directly in tests.
    """
    from notification_service.consumer import KafkaEventConsumer
    from notification_service.handler import EventHandler
    from notification_service.producer import KafkaStatusProducer

    kafka_config = KafkaConfig()
    group_id = f"test-{uuid.uuid4().hex[:8]}"
    consumer = KafkaEventConsumer(kafka_config, group_id)
    status_producer = KafkaStatusProducer(kafka_config)

    celery_app = Celery(broker=redis_url)

    handler = EventHandler(session_factory, celery_app, status_producer)

    stop_event = threading.Event()
    error_holder: list[Exception] = []

    def _loop() -> None:
        while not stop_event.is_set():
            try:
                msg = consumer.poll(timeout=0.5)
            except Exception as exc:
                error_holder.append(exc)
                break
            if msg is None:
                continue
            try:
                raw: dict[str, Any] = json.loads(msg.value().decode("utf-8"))
                handler.handle(raw)
            except ValueError:
                pass  # invalid event, skip (same as real service)
            except Exception as exc:
                error_holder.append(exc)
            consumer.commit(msg)

    thread = threading.Thread(target=_loop, daemon=True)
    thread.start()

    yield

    stop_event.set()
    thread.join(timeout=5)
    consumer.close()
    status_producer.close()


# ---------------------------------------------------------------------------
# Kafka delivery status consumer (helper for verifying status events)
# ---------------------------------------------------------------------------


@pytest.fixture()
def delivery_status_messages(
    kafka_bootstrap: str,
    kafka_topics: list[str],
) -> Generator[list[dict[str, Any]], None, None]:
    """Collect messages from notification.delivery topic in background."""
    group_id = f"test-status-{uuid.uuid4().hex[:8]}"
    raw_consumer = KafkaRawConsumer({
        "bootstrap.servers": kafka_bootstrap,
        "group.id": group_id,
        "auto.offset.reset": "latest",
        "enable.auto.commit": True,
    })
    raw_consumer.subscribe(["notification.delivery"])

    messages: list[dict[str, Any]] = []
    stop_event = threading.Event()

    def _loop() -> None:
        while not stop_event.is_set():
            msg = raw_consumer.poll(timeout=0.5)
            if msg is None:
                continue
            err = msg.error()
            if err is not None:
                if err.code() == KafkaError._PARTITION_EOF:
                    continue
                break
            try:
                data = json.loads(msg.value().decode("utf-8"))
                messages.append(data)
            except (json.JSONDecodeError, UnicodeDecodeError):
                pass

    thread = threading.Thread(target=_loop, daemon=True)
    thread.start()

    yield messages

    stop_event.set()
    thread.join(timeout=5)
    raw_consumer.close()
