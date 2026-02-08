from pydantic_settings import BaseSettings, SettingsConfigDict


class CeleryConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="CELERY_")

    broker_url: str = "redis://localhost:6379/0"


class RateLimitConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="RATE_LIMIT_")

    email_per_minute: int = 100
    sms_per_minute: int = 50
    push_per_minute: int = 200
    window_seconds: int = 60

    def limit_for_channel(self, channel: str) -> int:
        """Return the per-minute limit for a given channel."""
        limits = {
            "email": self.email_per_minute,
            "sms": self.sms_per_minute,
            "push": self.push_per_minute,
        }
        limit = limits.get(channel)
        if limit is None:
            raise ValueError(f"Unknown channel: {channel!r}")
        return limit


class DeliveryConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="DELIVERY_")

    log_level: str = "INFO"
    provider_timeout_seconds: int = 30
    retry_backoff_seconds: list[int] = [60, 300, 900]
