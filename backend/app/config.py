from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[1] / ".env",
        extra="ignore",
        hide_input_in_errors=True,
    )

    database_url: str = "postgresql+psycopg://dietary:dietary@localhost:5432/dietary"
    jwt_secret: SecretStr
    token_minutes: int = Field(default=30, ge=1, le=1440)
    cors_origins: list[str] = ["http://localhost:8081", "http://localhost:19006"]
    off_user_agent: str = "DietaryRiskPrototype/0.1 (local hackathon prototype)"
    provider_timeout: float = Field(default=20, gt=0, le=60)
    apify_token: SecretStr | None = None
    typesafe_api_key: SecretStr | None = None
    typesafe_model: str = "jev-1.13.0"
    fireworks_api_key: SecretStr | None = None
    fireworks_model: str = "accounts/fireworks/models/deepseek-v4p1-flash"
    label_timeout: float = Field(default=45, gt=0, le=90)
    label_max_tokens: int = Field(default=2048, ge=128, le=4096)
    # Health-report reading is a bigger document than a label, so it gets its own
    # timeout, output budget, upload cap and page cap.
    report_timeout: float = Field(default=60, gt=0, le=120)
    report_max_tokens: int = Field(default=3072, ge=128, le=8192)
    report_max_bytes: int = Field(default=10 * 1024 * 1024, ge=1024)
    report_max_pages: int = Field(default=5, ge=1, le=20)
    # Per-process token-bucket rate limiting. Limits are resolved per request, so
    # changing them (or RATE_LIMIT_ENABLED) takes effect without a rebuild.
    rate_limit_enabled: bool = True
    rate_limit_auth_per_minute: int = Field(default=10, ge=1, le=10000)
    rate_limit_label_extract_per_minute: int = Field(default=10, ge=1, le=10000)
    rate_limit_report_extract_per_minute: int = Field(default=10, ge=1, le=10000)
    rate_limit_provider_reads_per_minute: int = Field(default=30, ge=1, le=10000)
    rate_limit_recommendations_per_minute: int = Field(default=20, ge=1, le=10000)
    # Reject any request body larger than this before a route can buffer it.
    max_body_bytes: int = Field(default=6 * 1024 * 1024, ge=1024)
    log_level: str = "INFO"

    @field_validator("apify_token", "typesafe_api_key", "fireworks_api_key", mode="before")
    @classmethod
    def empty_key(cls, value):
        return None if value == "" else value

    @field_validator("jwt_secret")
    @classmethod
    def strong_secret(cls, value):
        if len(value.get_secret_value()) < 32 or value.get_secret_value().startswith("replace-"):
            raise ValueError("JWT_SECRET must have at least 32 characters")
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
