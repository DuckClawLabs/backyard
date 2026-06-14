"""Server configuration loaded from environment variables."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Database
    database_url: str = "postgresql+asyncpg://backyard:backyard@localhost:5432/backyard"

    # Redis
    redis_url: str = "redis://localhost:6379"

    # Anthropic (for file summaries and activity compression)
    anthropic_api_key: str = ""

    # Auth — optional. If empty, auth is disabled and identity comes from me.yaml.
    # When set, every request must present a matching Bearer token.
    # Format: comma-separated keys, e.g. key-alice,key-bob
    api_keys: str = ""

    # Server
    base_url: str = "http://localhost:8000"
    log_level: str = "INFO"

    # Briefing
    briefing_max_tokens: int = 2000
    activity_compression_interval: int = 10  # compress every N turns

    # Audit
    audit_retention_days: int = 365

    @property
    def valid_api_keys(self) -> set[str]:
        return {k.strip() for k in self.api_keys.split(",") if k.strip()}

    @property
    def auth_enabled(self) -> bool:
        return bool(self.valid_api_keys)


settings = Settings()
