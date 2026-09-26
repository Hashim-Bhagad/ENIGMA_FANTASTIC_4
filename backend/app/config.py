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
    theverifico_api_key: SecretStr | None = None
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
    # Drafting a short ingredient list is a small text call, but the configured model reasons
    # before it answers, so the output budget must cover the reasoning trace plus the JSON.
    dish_draft_timeout: float = Field(default=45, gt=0, le=120)
    dish_draft_max_tokens: int = Field(default=3072, ge=128, le=8192)
    # The wording fallback is a text call of the same shape as the draft, on a model that
    # reasons before it answers, so its budget also has to cover the reasoning trace.
    # One dish check can spend this twice (wording review, then swap suggestions), so the
    # whole model section stays bounded well inside the client's request timeout.
    dish_review_timeout: float = Field(default=45, gt=0, le=120)
    dish_review_max_tokens: int = Field(default=5120, ge=128, le=8192)
    # Live Food.com recipe search. The actor charges per returned result, so
    # recipes_live_max_items is the spend cap and recipes_live_timeout_seconds
    # bounds the wall clock; both are enforced in app/services/recipes_live.py.
    recipes_live_enabled: bool = True
    recipes_live_max_items: int = Field(default=5, ge=1, le=20)
    recipes_live_timeout_seconds: int = Field(default=120, ge=10, le=300)
    # Per-process token-bucket rate limiting. Limits are resolved per request, so
    # changing them (or RATE_LIMIT_ENABLED) takes effect without a rebuild.
    rate_limit_enabled: bool = True
    rate_limit_auth_per_minute: int = Field(default=10, ge=1, le=10000)
    rate_limit_label_extract_per_minute: int = Field(default=10, ge=1, le=10000)
    rate_limit_report_extract_per_minute: int = Field(default=10, ge=1, le=10000)
    rate_limit_provider_reads_per_minute: int = Field(default=30, ge=1, le=10000)
    rate_limit_recommendations_per_minute: int = Field(default=20, ge=1, le=10000)
    rate_limit_barcode_scan_per_minute: int = Field(default=20, ge=1, le=10000)
    rate_limit_dish_draft_per_minute: int = Field(default=10, ge=1, le=10000)
    rate_limit_dish_review_per_minute: int = Field(default=10, ge=1, le=10000)
    rate_limit_recipes_live_per_minute: int = Field(default=5, ge=1, le=10000)
    # Reject any request body larger than this before a route can buffer it.
    # Phone photos are routinely 5-10 MiB; the upload routes keep their own tighter caps
    # and explain them, so this ceiling only stops runaway bodies.
    max_body_bytes: int = Field(default=16 * 1024 * 1024, ge=1024)
    log_level: str = "INFO"

    @field_validator(
        "apify_token",
        "theverifico_api_key",
        "typesafe_api_key",
        "fireworks_api_key",
        mode="before",
    )
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
