from functools import lru_cache
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

from pydantic import Field, HttpUrl, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Validated application settings loaded from the repository-root .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "Pliris BA Bot"
    app_env: Literal["development", "test", "production"] = "development"
    log_level: str = "INFO"
    api_host: str = "0.0.0.0"
    api_port: int = Field(default=8000, ge=1, le=65535)

    openai_api_key: SecretStr
    openai_chat_model: str = "gpt-5-mini"
    openai_embedding_model: str = "text-embedding-3-small"
    openai_embedding_dimensions: int = Field(default=1536, ge=1)

    supabase_url: HttpUrl
    supabase_publishable_key: SecretStr
    supabase_secret_key: SecretStr
    supabase_db_url: SecretStr
    supabase_storage_bucket: str = "knowledge-base"

    postgres_pool_min_size: int = Field(default=0, ge=0)
    postgres_pool_max_size: int = Field(default=5, ge=1)
    postgres_connect_timeout_seconds: int = Field(default=15, ge=1, le=120)

    retrieval_match_count: int = Field(default=8, ge=1, le=100)
    retrieval_candidate_count: int = Field(default=32, ge=1, le=200)
    full_text_weight: float = Field(default=1.0, ge=0)
    semantic_weight: float = Field(default=1.0, ge=0)
    rrf_k: int = Field(default=50, ge=1)
    enable_query_rewriting: bool = True
    enable_reranking: bool = True

    enable_scope_guardrail: bool = True
    scope_confidence_threshold: float = Field(default=0.75, ge=0, le=1)
    out_of_scope_message: str = (
        "Pliris BA Bot is designed to assist with Business Analysis, "
        "Business Systems Analysis, and Project Management practices. "
        "Please ask a question related to one of these areas."
    )

    private_document_directory: Path = Path("data/private")
    corpus_manifest_path: Path = Path("data/corpus_manifest.yaml")
    chunk_size_tokens: int = Field(default=700, ge=100, le=4000)
    chunk_overlap_tokens: int = Field(default=100, ge=0, le=1000)

    enable_monitoring: bool = True
    enable_feedback: bool = True

    @field_validator("supabase_storage_bucket")
    @classmethod
    def validate_bucket_name(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("SUPABASE_STORAGE_BUCKET cannot be empty.")
        return cleaned

    @field_validator("openai_chat_model", "openai_embedding_model")
    @classmethod
    def validate_non_empty_model_name(cls, value: str) -> str:
        cleaned = value.strip()

        if not cleaned:
            raise ValueError("OpenAI model names cannot be empty.")

        return cleaned

    @field_validator(
        "openai_api_key",
        "supabase_publishable_key",
        "supabase_secret_key",
    )
    @classmethod
    def validate_non_empty_secret(cls, value: SecretStr) -> SecretStr:
        if not value.get_secret_value().strip():
            raise ValueError("Required secret values cannot be empty.")

        return value

    @field_validator("supabase_db_url")
    @classmethod
    def validate_database_url(cls, value: SecretStr) -> SecretStr:
        raw_value = value.get_secret_value()
        parsed = urlparse(raw_value)
        if parsed.scheme not in {"postgres", "postgresql"}:
            raise ValueError("SUPABASE_DB_URL must start with postgres:// or postgresql://.")
        if not parsed.hostname:
            raise ValueError("SUPABASE_DB_URL must include a database host.")
        return value

    @model_validator(mode="after")
    def validate_related_settings(self) -> "Settings":
        if self.postgres_pool_min_size > self.postgres_pool_max_size:
            raise ValueError("POSTGRES_POOL_MIN_SIZE cannot exceed POSTGRES_POOL_MAX_SIZE.")

        if self.retrieval_candidate_count < self.retrieval_match_count:
            raise ValueError("RETRIEVAL_CANDIDATE_COUNT must be at least RETRIEVAL_MATCH_COUNT.")

        if self.full_text_weight == 0 and self.semantic_weight == 0:
            raise ValueError("At least one retrieval weight must be greater than zero.")

        if (
            self.openai_embedding_model == "text-embedding-3-small"
            and self.openai_embedding_dimensions != 1536
        ):
            raise ValueError(
                "The current Supabase schema uses vector(1536). "
                "Set OPENAI_EMBEDDING_DIMENSIONS=1536."
            )

        return self

    @property
    def supabase_url_string(self) -> str:
        return str(self.supabase_url).rstrip("/")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return one validated Settings instance for the current process."""
    return Settings()


# Compatibility export for modules that use:
# from pliris.config.settings import settings
settings = get_settings()
