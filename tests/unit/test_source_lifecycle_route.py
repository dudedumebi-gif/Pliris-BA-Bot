from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.developer_access import require_developer_access
from api.routes.source_lifecycle import (
    get_source_lifecycle_repository,
    router,
)
from pliris.database.repositories.source_lifecycle import (
    SourceConfirmationError,
    SourceLifecycleConflictError,
    SourceNotFoundError,
)


class FakeRepository:
    def __init__(self) -> None:
        self.document_id = uuid4()
        self.mode = "success"

    def _result(self, action: str) -> dict:
        previous = "ready" if action == "archive" else "archived"
        new = "archived" if action == "archive" else "ready"
        return {
            "id": uuid4(),
            "document_id": self.document_id,
            "action": action,
            "actor": "developer-api",
            "reason": "Lifecycle acceptance test.",
            "previous_status": previous,
            "new_status": new,
            "metadata": {},
            "created_at": datetime.now(UTC),
        }

    async def archive(self, *_: object, **__: object):
        return self._apply("archive")

    async def restore(self, *_: object, **__: object):
        return self._apply("restore")

    async def list_events(self, *_: object, **__: object):
        return [self._result("archive")], 1

    def _apply(self, action: str):
        if self.mode == "not_found":
            raise SourceNotFoundError
        if self.mode == "confirmation":
            raise SourceConfirmationError
        if self.mode == "conflict":
            raise SourceLifecycleConflictError
        return self._result(action)


def _client():
    repository = FakeRepository()
    app = FastAPI()
    app.include_router(router, prefix="/api/sources")
    app.dependency_overrides[require_developer_access] = lambda: None
    app.dependency_overrides[get_source_lifecycle_repository] = lambda: repository
    return TestClient(app), repository


def _payload() -> dict[str, str]:
    return {
        "reason": "Lifecycle acceptance test.",
        "confirmation": "gao-agile-assessment-guide-2023",
    }


def test_lifecycle_routes_succeed() -> None:
    client, repository = _client()

    archive = client.post(
        f"/api/sources/{repository.document_id}/archive",
        json=_payload(),
    )
    restore = client.post(
        f"/api/sources/{repository.document_id}/restore",
        json=_payload(),
    )
    events = client.get(
        f"/api/sources/{repository.document_id}/events",
    )

    assert archive.status_code == 200
    assert archive.json()["new_status"] == "archived"
    assert restore.status_code == 200
    assert restore.json()["new_status"] == "ready"
    assert events.status_code == 200
    assert events.json()["total"] == 1


def test_lifecycle_routes_map_safe_errors() -> None:
    client, repository = _client()
    path = f"/api/sources/{repository.document_id}/archive"

    repository.mode = "confirmation"
    assert client.post(path, json=_payload()).status_code == 400

    repository.mode = "conflict"
    assert client.post(path, json=_payload()).status_code == 409

    repository.mode = "not_found"
    assert client.post(path, json=_payload()).status_code == 404


def test_lifecycle_route_rejects_reason_that_is_short_after_stripping() -> None:
    client, repository = _client()

    response = client.post(
        f"/api/sources/{repository.document_id}/archive",
        json={
            "reason": "      short      ",
            "confirmation": "gao-agile-assessment-guide-2023",
        },
    )

    assert response.status_code == 422
