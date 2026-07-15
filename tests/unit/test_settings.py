from pydantic import SecretStr

from pliris.config.settings import Settings


def valid_settings() -> Settings:
    return Settings(
        _env_file=None,
        openai_api_key=SecretStr("test-openai-key"),
        supabase_url="https://example.supabase.co",
        supabase_publishable_key=SecretStr("test-publishable-key"),
        supabase_secret_key=SecretStr("test-secret-key"),
        supabase_db_url=SecretStr(
            "postgresql://postgres.example:password@example.pooler.supabase.com:5432/postgres"
        ),
    )


def test_settings_accept_the_approved_embedding_contract() -> None:
    settings = valid_settings()
    assert settings.openai_embedding_model == "text-embedding-3-small"
    assert settings.openai_embedding_dimensions == 1536


def test_settings_use_hybrid_retrieval_defaults() -> None:
    settings = valid_settings()
    assert settings.full_text_weight > 0
    assert settings.semantic_weight > 0
    assert settings.retrieval_candidate_count >= settings.retrieval_match_count
