import os
from unittest.mock import patch

from shared.config import KafkaConfig, PostgresConfig, RedisConfig


class TestKafkaConfig:
    def test_defaults(self):
        config = KafkaConfig()
        assert config.bootstrap_servers == "localhost:9092"
        assert config.domain_events_topic == "domain.events"
        assert config.delivery_events_topic == "notification.delivery"

    def test_from_env(self):
        env = {
            "KAFKA_BOOTSTRAP_SERVERS": "broker1:9092,broker2:9092",
            "KAFKA_DOMAIN_EVENTS_TOPIC": "prod.domain.events",
            "KAFKA_DELIVERY_EVENTS_TOPIC": "prod.delivery",
        }
        with patch.dict(os.environ, env, clear=False):
            config = KafkaConfig()
        assert config.bootstrap_servers == "broker1:9092,broker2:9092"
        assert config.domain_events_topic == "prod.domain.events"
        assert config.delivery_events_topic == "prod.delivery"


class TestRedisConfig:
    def test_defaults(self):
        config = RedisConfig()
        assert config.host == "localhost"
        assert config.port == 6379
        assert config.db == 0

    def test_from_env(self):
        env = {
            "REDIS_HOST": "redis.prod",
            "REDIS_PORT": "6380",
            "REDIS_DB": "2",
        }
        with patch.dict(os.environ, env, clear=False):
            config = RedisConfig()
        assert config.host == "redis.prod"
        assert config.port == 6380
        assert config.db == 2


class TestPostgresConfig:
    def test_defaults(self):
        config = PostgresConfig()
        assert config.host == "localhost"
        assert config.port == 5432
        assert config.database == "notifications"
        assert config.user == "postgres"
        assert config.password == "postgres"

    def test_dsn(self):
        config = PostgresConfig()
        assert config.dsn == "postgresql://postgres:postgres@localhost:5432/notifications"

    def test_dsn_from_env(self):
        env = {
            "POSTGRES_HOST": "db.prod",
            "POSTGRES_PORT": "5433",
            "POSTGRES_DATABASE": "notif_prod",
            "POSTGRES_USER": "app",
            "POSTGRES_PASSWORD": "s3cret",
        }
        with patch.dict(os.environ, env, clear=False):
            config = PostgresConfig()
        assert config.dsn == "postgresql://app:s3cret@db.prod:5433/notif_prod"

    def test_port_validation(self):
        env = {"POSTGRES_PORT": "not_a_number"}
        with patch.dict(os.environ, env, clear=False):
            try:
                PostgresConfig()
                assert False, "Should have raised"
            except Exception:
                pass
