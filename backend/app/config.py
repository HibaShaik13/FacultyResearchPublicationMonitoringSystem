"""
Application configuration using Pydantic Settings.
All configuration is loaded from environment variables / .env file.
"""

from functools import lru_cache
from typing import List

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central application configuration."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Application ---
    app_name: str = "Faculty Research Publication Monitoring System"
    app_env: str = "development"
    debug: bool = True
    log_level: str = "INFO"

    # --- Backend Server ---
    backend_host: str = "0.0.0.0"
    backend_port: int = 8000
    backend_cors_origins: List[str] = Field(
        default=["http://localhost:5173", "http://localhost:3000"]
    )

    @field_validator("backend_cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v):
        if isinstance(v, str):
            import json
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                return [origin.strip() for origin in v.split(",")]
        return v

    # --- Database ---
    database_url: str = ""
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "research_monitoring"
    postgres_user: str = "research_admin"
    postgres_password: str = "changeme_in_production"

    @property
    def database_url_property(self) -> str:
        if self.database_url:
            url = self.database_url
            if url.startswith("postgres://"):
                url = url.replace("postgres://", "postgresql+asyncpg://", 1)
            elif url.startswith("postgresql://") and "+asyncpg" not in url:
                url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
            return url
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def database_url_sync_property(self) -> str:
        """Synchronous URL for Alembic migrations."""
        if self.database_url:
            url = self.database_url
            if url.startswith("postgres://"):
                url = url.replace("postgres://", "postgresql://", 1)
            return url.replace("+asyncpg", "").replace("+aiosqlite", "")
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def database_url_sync(self) -> str:
        """Alias for database_url_sync_property."""
        return self.database_url_sync_property

    # --- Redis ---
    redis_host: str = "localhost"
    redis_port: int = 6379

    @property
    def redis_url(self) -> str:
        return f"redis://{self.redis_host}:{self.redis_port}/0"

    @property
    def celery_broker_url(self) -> str:
        return f"redis://{self.redis_host}:{self.redis_port}/0"

    @property
    def celery_result_backend(self) -> str:
        return f"redis://{self.redis_host}:{self.redis_port}/1"

    # --- JWT ---
    jwt_secret_key: str = "CHANGE_THIS_TO_A_RANDOM_64_CHAR_STRING"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 30
    jwt_refresh_token_expire_days: int = 7

    # --- LLM ---
    groq_api_key: str = ""
    groq_model: str = "llama-3.1-70b-versatile"

    # --- Research APIs ---
    openalex_email: str = ""
    crossref_email: str = ""
    semantic_scholar_api_key: str = ""
    orcid_client_id: str = ""
    orcid_client_secret: str = ""

    # --- Optional Enterprise APIs ---
    scopus_api_key: str = ""
    scopus_inst_token: str = ""
    wos_api_key: str = ""
    google_scholar_serpapi_key: str = ""

    # --- Sync Schedule ---
    sync_full_discovery: str = "0 2 * * 0"
    sync_citation_refresh: str = "0 3 * * 3"
    sync_metrics_compute: str = "0 4 * * 3"
    sync_alert_generation: str = "0 5 * * *"
    sync_report_generation: str = "0 6 1 * *"

    # --- Institution ---
    institution_name: str = "Vignan's Foundation for Science, Technology & Research"
    institution_short: str = "VFSTR"

    # --- Production Bootstrap / Seeding ---
    bootstrap_admin_email: str = "admin@vignan.ac.in"
    bootstrap_admin_password: str = "admin"
    bootstrap_admin_name: str = "System Administrator"
    bootstrap_faculty_password: str = "faculty123"
    bootstrap_seed_faculty: bool = True


@lru_cache
def get_settings() -> Settings:
    """Cached singleton for application settings."""
    return Settings()
