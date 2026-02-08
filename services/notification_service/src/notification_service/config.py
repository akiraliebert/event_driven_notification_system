from pydantic_settings import BaseSettings, SettingsConfigDict


class NotificationServiceConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="NOTIFICATION_SERVICE_")

    log_level: str = "INFO"
    kafka_group_id: str = "notification-service"


class CeleryConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="CELERY_")

    broker_url: str = "redis://localhost:6379/0"
