"""
Centralized application configuration.

Uses pydantic-settings to load values from environment variables / .env file.
All security-sensitive values are kept here and never leaked to logs or LLM.
"""

from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from .env file."""

    model_config = SettingsConfigDict(
        env_file=str(Path(__file__).resolve().parents[2] / ".env"),
        env_file_encoding="utf-8",
    )

    # ── Security ──
    SECRET_KEY: str = "change-me"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # ── Database ──
    DATABASE_PATH: str = "./data/analytics.duckdb"

    # ── Query safety ──
    DEFAULT_QUERY_LIMIT: int = 1000
    QUERY_TIMEOUT_SECONDS: int = 10

    # ── Rate limiting ──
    RATE_LIMIT_PER_MINUTE: int = 60

    # ── LLM provider (stub | openai | gemini) ──
    LLM_PROVIDER: str = "stub"
    GEMINI_API_KEY: str | None = None


# Singleton instance used across the application
settings = Settings()
