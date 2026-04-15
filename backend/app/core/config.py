"""
core/config.py — Environment-driven configuration via Pydantic Settings.
All secrets and tunable knobs live here; never hard-code in business logic.
"""
from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # ── Application ──────────────────────────────────────────────────────────
    APP_NAME: str = "FlowPriceAI"
    APP_VERSION: str = "1.0.0"
    ENVIRONMENT: Literal["development", "staging", "production"] = "development"
    DEBUG: bool = True
    API_V1_PREFIX: str = "/api/v1"

    # ── Security ─────────────────────────────────────────────────────────────
    SECRET_KEY: str = Field(default="dev-secret-change-in-production-min-32-chars")

    # ✅ 🔥 ADDED JWT CONFIG (THIS FIXES YOUR LOGIN ERROR)
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440

    API_KEY_HEADER: str = "X-API-Key"
    INTERNAL_API_KEY: str = Field(default="internal-dev-key")
    CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:3001"]

    # ── Redis ─────────────────────────────────────────────────────────────────
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_MAX_CONNECTIONS: int = 50
    REDIS_SOCKET_TIMEOUT: float = 1.0
    REDIS_CONNECT_TIMEOUT: float = 2.0

    # Stream configuration
    EVENTS_STREAM_KEY: str = "events:clickstream"
    EVENTS_CONSUMER_GROUP: str = "feature-computers"
    EVENTS_CONSUMER_NAME: str = "worker-1"
    STREAM_MAX_LEN: int = 100_000
    STREAM_BLOCK_MS: int = 100
    STREAM_BATCH_SIZE: int = 50

    # Feature store TTLs
    SESSION_FEATURE_TTL: int = 1_800
    USER_FEATURE_TTL: int = 86_400
    PRODUCT_DEMAND_TTL: int = 60
    PRICING_CACHE_TTL: int = 30

    # ── Database ──────────────────────────────────────────────────────────────
    DATABASE_URL: str = "sqlite+aiosqlite:///./pricing_engine.db"
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20

    # ── Pricing Engine ────────────────────────────────────────────────────────
    MIN_MARGIN_PCT: float = 0.10
    MAX_DISCOUNT_PCT: float = 0.40
    MAX_SURGE_PCT: float = 0.25
    PRICE_PARITY_WINDOW_HOURS: int = 24

    HIGH_DEMAND_THRESHOLD: int = 50
    LOW_DEMAND_THRESHOLD: int = 5
    DEMAND_VELOCITY_WINDOW_SECONDS: int = 300

    DEMAND_WEIGHT: float = 0.35
    INVENTORY_WEIGHT: float = 0.25
    COMPETITOR_WEIGHT: float = 0.20
    SEGMENT_WEIGHT: float = 0.20

    # ── Recommendation Engine ─────────────────────────────────────────────────
    RECOMMENDATION_COUNT: int = 10
    CF_MODEL_PATH: str = "ml/models/cf_model.pkl"
    GRU_MODEL_PATH: str = "ml/models/gru4rec.pt"
    COLD_START_FALLBACK_COUNT: int = 10

    GRU_HIDDEN_SIZE: int = 128
    GRU_NUM_LAYERS: int = 2
    GRU_DROPOUT: float = 0.3
    MAX_SESSION_LENGTH: int = 50

    # ── A/B Testing ───────────────────────────────────────────────────────────
    AB_ENABLED: bool = True
    AB_SALT: str = "pricing-ab-2024"
    DEFAULT_EXPERIMENT_TRAFFIC_PCT: float = 0.5

    # ── Vendor / SMTP ─────────────────────────────────────────────────────────
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = "rdvraval19@gmail.com"          # e.g. yourapp@gmail.com
    SMTP_PASSWORD: str = "bvwcsrvekugbczzt"          # Gmail App Password
    SMTP_FROM_NAME: str = "FlowPriceAI Deals"
 
    # Coupon defaults
    COUPON_DEFAULT_TTL_MINUTES: int = 1440   # 24 hours
    COUPON_CODE_LENGTH: int = 8


    # ── Observability ─────────────────────────────────────────────────────────
    LATENCY_P99_TARGET_MS: float = 200.0
    METRICS_WINDOW_SECONDS: int = 60

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors(cls, v: str | list) -> list[str]:
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"

    @property
    def redis_stream_config(self) -> dict:
        return {
            "stream_key": self.EVENTS_STREAM_KEY,
            "group": self.EVENTS_CONSUMER_GROUP,
            "consumer": self.EVENTS_CONSUMER_NAME,
            "max_len": self.STREAM_MAX_LEN,
            "block_ms": self.STREAM_BLOCK_MS,
            "batch_size": self.STREAM_BATCH_SIZE,
        }


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


settings = get_settings()