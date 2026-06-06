from __future__ import annotations

from typing import Self

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_DEV_JWT_PLACEHOLDER = "mythos-aegis-dev-secret-change-in-production"
_MIN_PRODUCTION_SECRET_LEN = 32


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/mythos_aegis"  # pragma: allowlist secret  # noqa: E501
    APP_ENV: str = "development"
    INTENT_CONFIDENCE_THRESHOLD: float = 0.85
    SQL_TIMEOUT_SECONDS: int = 3
    SQL_MAX_LIMIT: int = 100

    # Redis — used for rate limiting.  Graceful degradation when unavailable.
    REDIS_URL: str = "redis://localhost:6379/0"

    # OpenTelemetry — disabled by default; set OTEL_ENABLED=true in production.
    OTEL_ENABLED: bool = False
    OTEL_EXPORTER_OTLP_ENDPOINT: str = "http://localhost:4318/v1/traces"
    OTEL_SERVICE_NAME: str = "mythos-aegis"

    # JWT settings
    JWT_SECRET: str = _DEV_JWT_PLACEHOLDER
    # Previous signing key — set during key rotation so outstanding tokens
    # issued with the old key remain valid until they expire.
    # Empty string means "no previous key configured".
    JWT_PREVIOUS_SECRET: str = ""
    JWT_ALGORITHM: str = "HS256"
    JWT_ISSUER: str = "mythos-aegis"
    JWT_AUDIENCE: str = "mythos-aegis-api"
    JWT_EXPIRY_SECONDS: int = 3600

    # ── RAG / Embedding ───────────────────────────────────────────────────────
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "qwen2.5:1.5b"
    OLLAMA_TIMEOUT: float = 60.0
    RAG_EMBEDDING_MODEL: str = "nomic-embed-text"
    RAG_EMBEDDING_DIMENSION: int = 768
    RAG_CHUNK_SIZE: int = 512
    RAG_CHUNK_OVERLAP: int = 50
    RAG_MAX_FILE_SIZE_MB: int = 10
    RAG_MAX_FILE_SIZE_BYTES: int = 10 * 1024 * 1024
    RAG_TOP_K: int = 5

    # ── AI Gateway ────────────────────────────────────────────────────────────
    AI_QUOTA_ENABLED: bool = True
    AI_MONTHLY_REQUEST_LIMIT: int = 1000

    # ── Vision Intelligence ───────────────────────────────────────────────────
    VISION_MODEL: str = "qwen2.5-vl:7b"
    VISION_FALLBACK_MODEL: str = "llama3.2-vision:11b"
    VISION_MAX_IMAGE_SIZE_MB: int = 20
    VISION_MAX_IMAGE_SIZE_BYTES: int = 20 * 1024 * 1024
    VISION_ANALYSIS_TIMEOUT: float = 120.0

    # ── Agent Runtime ─────────────────────────────────────────────────────────
    AGENT_MODEL: str = "qwen2.5:1.5b"
    AGENT_MAX_ITERATIONS: int = 5
    AGENT_MAX_CONTEXT_CHARS: int = 8_000

    # ── Workflow Engine ───────────────────────────────────────────────────────
    WORKFLOW_MAX_STEPS: int = 20
    WORKFLOW_STEP_TIMEOUT: float = 300.0
    WORKFLOW_MAX_RETRY_ATTEMPTS: int = 5

    # ── Billing ───────────────────────────────────────────────────────────────
    BILLING_PROVIDER: str = "mock"  # mock | stripe
    STRIPE_SECRET_KEY: str = ""  # only read when BILLING_PROVIDER=stripe
    STRIPE_WEBHOOK_SECRET: str = ""  # only read when BILLING_PROVIDER=stripe

    # ── Field validators ──────────────────────────────────────────────────────

    @field_validator("APP_ENV")
    @classmethod
    def validate_app_env(cls, v: str) -> str:
        allowed = {"development", "staging", "production"}
        if v not in allowed:
            raise ValueError(f"APP_ENV must be one of {allowed}")
        return v

    @field_validator("INTENT_CONFIDENCE_THRESHOLD")
    @classmethod
    def validate_confidence_threshold(cls, v: float) -> float:
        if not 0.0 < v <= 1.0:
            raise ValueError(
                "INTENT_CONFIDENCE_THRESHOLD must be between 0.0 (exclusive) and 1.0"
            )
        return v

    @field_validator("SQL_TIMEOUT_SECONDS")
    @classmethod
    def validate_sql_timeout(cls, v: int) -> int:
        if v < 1 or v > 30:
            raise ValueError("SQL_TIMEOUT_SECONDS must be between 1 and 30")
        return v

    @field_validator("SQL_MAX_LIMIT")
    @classmethod
    def validate_sql_max_limit(cls, v: int) -> int:
        if v < 1 or v > 1000:
            raise ValueError("SQL_MAX_LIMIT must be between 1 and 1000")
        return v

    # ── Model validator (runs after all field validators) ─────────────────────

    @model_validator(mode="after")
    def validate_production_secrets(self) -> Self:
        """Refuse to start in production with a weak or default JWT secret.

        Fail loudly at startup rather than silently allowing an exploitable
        configuration.  Generate a strong secret with:
            python -c "import secrets; print(secrets.token_hex(32))"
        """
        if self.APP_ENV == "production" and (
            self.JWT_SECRET == _DEV_JWT_PLACEHOLDER
            or len(self.JWT_SECRET) < _MIN_PRODUCTION_SECRET_LEN
        ):
            raise ValueError(
                "JWT_SECRET must be a strong secret "
                f"(≥{_MIN_PRODUCTION_SECRET_LEN} characters and not the "
                "default dev value) when APP_ENV=production."
            )
        return self


settings = Settings()
