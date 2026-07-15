import sys

from psycopg.conninfo import conninfo_to_dict
from pydantic import ValidationError

from pliris.config.settings import get_settings


def _masked(value: str, visible: int = 6) -> str:
    if len(value) <= visible:
        return "*" * len(value)
    return f"{value[:visible]}...{value[-4:]}"


def main() -> int:
    try:
        settings = get_settings()
    except ValidationError as exc:
        print("Environment validation failed.")
        for error in exc.errors():
            location = ".".join(str(part) for part in error["loc"])
            print(f"  - {location}: {error['msg']}")
        return 1

    db_url = settings.supabase_db_url.get_secret_value()
    db_parameters = conninfo_to_dict(db_url)

    database_host = str(db_parameters.get("host") or "unknown")
    database_port = int(db_parameters.get("port") or 5432)

    print("Environment validation passed.")
    print(f"  App environment: {settings.app_env}")
    print(f"  Supabase host: {settings.supabase_url.host}")
    print(f"  Database host: {database_host}")
    print(f"  Database port: {database_port}")
    print(f"  Storage bucket: {settings.supabase_storage_bucket}")
    print(f"  Chat model: {settings.openai_chat_model}")
    print(
        "  Embedding contract: "
        f"{settings.openai_embedding_model} / "
        f"{settings.openai_embedding_dimensions} dimensions"
    )
    print(f"  Publishable key: {_masked(settings.supabase_publishable_key.get_secret_value())}")
    print(f"  Secret key: {_masked(settings.supabase_secret_key.get_secret_value())}")
    print(f"  OpenAI key: {_masked(settings.openai_api_key.get_secret_value())}")

    if database_port != 5432:
        print(
            "Warning: SUPABASE_DB_URL is not using port 5432. "
            "The approved development setup uses the Session Pooler."
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
