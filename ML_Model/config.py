"""
FinSight Configuration — Pydantic Settings loaded from environment variables.
"""

from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # ── Groq (sole external API) ──
    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "llama-3.3-70b-versatile"

    # ── Supabase ──
    SUPABASE_URL: str = "http://localhost:8002"
    SUPABASE_ANON_KEY: str = ""
    SUPABASE_SERVICE_KEY: str = ""
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/postgres"

    # ── Redis ──
    REDIS_URL: str = "redis://localhost:6379"

    # ── Security ──
    SECRET_KEY: str = "your_jwt_secret_min_32_chars_change_me"
    CERTIFICATE_PIN_SHA256: str = ""

    # ── Sync ──
    BACKFILL_BATCH_SIZE: int = 200
    BACKFILL_BATCH_DELAY_MS: int = 500
    CATCHUP_OVERLAP_DAYS: int = 7
    DEDUP_WINDOW_MS: int = 900_000  # 15 minutes

    # ── ML ──
    RETRAIN_THRESHOLD: int = 200
    RETRAIN_CHECK_INTERVAL_SEC: int = 300
    TFLITE_MODEL_VERSION: str = "2026.03.15"
    ONDEVICE_CONFIDENCE_THRESHOLD: float = 0.90

    # ── RL ──
    RL_BANDIT_ALPHA: float = 0.5
    RL_LEARNING_RATE: float = 0.01
    RL_MIN_UPDATES_BEFORE_SWITCH: int = 10

    # ── Bloom Filter ──
    BLOOM_CAPACITY: int = 10_000_000
    BLOOM_ERROR_RATE: float = 0.00001  # 0.001%

    # ── App ──
    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "info"

    # ── Analytics Cache ──
    ANALYTICS_CACHE_TTL: int = 300  # 5 minutes
    GROQ_CACHE_TTL: int = 1800  # 30 minutes

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


settings = Settings()
