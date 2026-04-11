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
    
    # ── Google OAuth2 ──
    GOOGLE_CLIENT_ID: str | None = None
    GOOGLE_CLIENT_SECRET: str | None = None

    # ── Database ──
    DATABASE_PATH: str = "./data/analytics.duckdb"
    REDIS_URL: str = "redis://localhost:6379/0"

    # ── Query safety ──
    DEFAULT_QUERY_LIMIT: int = 1000
    QUERY_TIMEOUT_SECONDS: int = 10

    # ── Rate limiting ──
    RATE_LIMIT_PER_MINUTE: int = 60

    # ── LLM provider (stub | groq) ──
    LLM_PROVIDER: str = "groq"
    GROQ_API_KEY: str | None = None
    GROQ_MODEL: str = "llama-3.3-70b-versatile"

    # ── Vector RAG ──
    RAG_BACKEND: str = "keyword"  # keyword | vector
    VECTOR_SHADOW_MODE: bool = False
    EMBEDDING_MODEL_NAME: str = "sentence-transformers/all-MiniLM-L6-v2"
    VECTOR_INDEX_PATH: str = "./data/business_knowledge.faiss"


# Singleton instance used across the application
settings = Settings()
