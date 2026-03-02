from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import PostgresDsn, RedisDsn, field_validator


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    app_name: str = "telemetry-platform"
    environment: str = "development"
    debug: bool = False
    api_v1_prefix: str = "/api/v1"

    database_url: PostgresDsn
    database_replica_url: PostgresDsn | None = None
    db_pool_size: int = 10
    db_max_overflow: int = 20
    db_pool_timeout: int = 30
    db_echo: bool = False

    redis_url: RedisDsn = "redis://localhost:6379/0"  # type: ignore[assignment]
    redis_max_connections: int = 50

    rate_limit_requests: int = 1000
    rate_limit_window_seconds: int = 60

    cache_ttl_fleet_summary: int = 60
    cache_ttl_hourly_stats: int = 300
    cache_ttl_latest_event: int = 10
    cache_ttl_low_battery: int = 30

    @field_validator("environment")
    @classmethod
    def validate_environment(cls, v: str) -> str:
        allowed = {"development", "staging", "production"}
        if v not in allowed:
            raise ValueError(f"environment must be one of {allowed}")
        return v


settings = Settings()
