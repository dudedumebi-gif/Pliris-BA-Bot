from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from time import perf_counter
from typing import Annotated, Any

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse

from api.developer_access import require_developer_access
from pliris.config.settings import Settings, get_settings
from pliris.database.postgres import postgres_connection
from pliris.database.supabase_client import get_supabase_admin_client

router = APIRouter(prefix="/health", tags=["health"])

HealthProbe = tuple[str, Callable[[], None]]
HealthProbes = tuple[HealthProbe, ...]


def _check_supabase_data_api() -> None:
    client = get_supabase_admin_client()
    client.table("documents").select("id").limit(1).execute()


def _check_postgres() -> None:
    with postgres_connection() as connection, connection.cursor() as cursor:
        cursor.execute("select 1 as ok")
        row = cursor.fetchone()
        if not row or row["ok"] != 1:
            raise RuntimeError("PostgreSQL readiness check did not return success.")


def get_health_probes() -> HealthProbes:
    """Return dependency probes through an overrideable FastAPI dependency."""

    return (
        ("supabase_data_api", _check_supabase_data_api),
        ("postgres", _check_postgres),
    )


def _run_probe(name: str, probe: Callable[[], None]) -> dict[str, str | float]:
    started = perf_counter()
    probe_status = "healthy"
    try:
        probe()
    except Exception:
        probe_status = "unavailable"
    latency_ms = round(max(0.0, (perf_counter() - started) * 1000), 2)
    return {
        "name": name,
        "status": probe_status,
        "latency_ms": latency_ms,
    }


def _run_dependency_probes(probes: HealthProbes) -> list[dict[str, str | float]]:
    return [_run_probe(name, probe) for name, probe in probes]


def _is_ready(checks: list[dict[str, str | float]]) -> bool:
    return all(check["status"] == "healthy" for check in checks)


def _safe_configuration(settings: Settings) -> dict[str, Any]:
    return {
        "app_name": settings.app_name,
        "app_env": settings.app_env,
        "chat_model": settings.openai_chat_model,
        "embedding_model": settings.openai_embedding_model,
        "embedding_dimensions": settings.openai_embedding_dimensions,
        "storage_bucket": settings.supabase_storage_bucket,
        "monitoring_enabled": settings.enable_monitoring,
        "feedback_enabled": settings.enable_feedback,
    }


@router.get("/live")
def live() -> dict[str, str]:
    """Liveness reveals only that the API process can receive requests."""

    return {"status": "ok"}


@router.get("/ready")
def ready(
    probes: Annotated[HealthProbes, Depends(get_health_probes)],
) -> JSONResponse:
    """Public readiness returns no dependency names or private failures."""

    checks = _run_dependency_probes(probes)
    ready_now = _is_ready(checks)
    response_status = status.HTTP_200_OK if ready_now else status.HTTP_503_SERVICE_UNAVAILABLE
    return JSONResponse(
        status_code=response_status,
        content={"status": "ready" if ready_now else "not_ready"},
    )


@router.get(
    "/config",
    dependencies=[Depends(require_developer_access)],
)
def non_secret_config(
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    """Return non-secret configuration only across the developer boundary."""

    return _safe_configuration(settings)


@router.get(
    "/diagnostics",
    dependencies=[Depends(require_developer_access)],
)
def diagnostics(
    probes: Annotated[HealthProbes, Depends(get_health_probes)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> JSONResponse:
    """Return protected, bounded liveness, readiness, and config diagnostics."""

    dependency_checks = _run_dependency_probes(probes)
    ready_now = _is_ready(dependency_checks)
    checks = [
        {"name": "api_process", "status": "healthy", "latency_ms": 0.0},
        *dependency_checks,
    ]
    payload = {
        "status": "ready" if ready_now else "not_ready",
        "checked_at": datetime.now(UTC).isoformat(),
        "checks": checks,
        "configuration": _safe_configuration(settings),
    }
    response_status = status.HTTP_200_OK if ready_now else status.HTTP_503_SERVICE_UNAVAILABLE
    return JSONResponse(status_code=response_status, content=payload)
