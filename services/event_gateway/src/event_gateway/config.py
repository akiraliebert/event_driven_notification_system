from pydantic_settings import BaseSettings, SettingsConfigDict


class GatewayConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="EVENT_GATEWAY_")

    host: str = "0.0.0.0"
    port: int = 8000
    log_level: str = "INFO"
