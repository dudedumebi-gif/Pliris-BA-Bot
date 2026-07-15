from typing import Any

from fastapi import APIRouter, status
from fastapi.responses import JSONResponse

from pliris.config.settings import get_settings
from pliris.database.postgres import postgres_connection
from pliris.database.supabase_client import get_supabase_admin_client

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/live")
def live() -> dict[str, str]:
    """Liveness means the API process can receive requests."""
    return {"status": "ok"}


@router.get("/ready")
def ready() -> JSONResponse:
    """Readiness verifies both Supabase Data API and PostgreSQL connectivity."""
    checks: dict[str, Any] = {
        "supabase_data_api": False,
        "postgres": False,
    }
    errors: list[str] = []

    try:
        client = get_supabase_admin_client()
        client.table("documents").select("id").limit(1).execute()
        checks["supabase_data_api"] = True
    except Exception as exc:
        errors.append(f"Supabase Data API: {type(exc).__name__}")

    try:
        with postgres_connection() as connection, connection.cursor() as cursor:
            cursor.execute("select 1 as ok")
            row = cursor.fetchone()
            checks["postgres"] = bool(row and row["ok"] == 1)
    except Exception as exc:
        errors.append(f"PostgreSQL: {type(exc).__name__}")

    payload = {
        "status": "ready" if all(checks.values()) else "not_ready",
        "checks": checks,
        "errors": errors,
    }

    response_status = (
        status.HTTP_200_OK if all(checks.values()) else status.HTTP_503_SERVICE_UNAVAILABLE
    )
    return JSONResponse(status_code=response_status, content=payload)


@router.get("/config")
def non_secret_config() -> dict[str, Any]:
    """Expose only safe configuration values for local diagnostics."""
    settings = get_settings()
    return {
        "app_name": settings.app_name,
        "app_env": settings.app_env,
        "chat_model": settings.openai_chat_model,
        "embedding_model": settings.openai_embedding_model,
        "embedding_dimensions": settings.openai_embedding_dimensions,
        "storage_bucket": settings.supabase_storage_bucket,
    }
