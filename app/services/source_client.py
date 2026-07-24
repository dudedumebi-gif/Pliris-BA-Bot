from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

from app.ui_config import UISettings

DEVELOPER_KEY_HEADER = "X-Pliris-Developer-Key"
_FORBIDDEN_RESPONSE_FIELDS = {
    "storage_path",
    "ingestion_error",
    "openai_api_key",
    "supabase_secret_key",
    "supabase_db_url",
    "embedding",
}


class SourceServiceError(RuntimeError):
    """Safe developer-UI failure raised by the source API client."""

    def __init__(
        self,
        *,
        code: str,
        user_message: str,
        status_code: int | None = None,
    ) -> None:
        super().__init__(user_message)
        self.code = code
        self.user_message = user_message
        self.status_code = status_code


@dataclass(frozen=True)
class SourceListPage:
    items: list[dict[str, Any]]
    total: int
    limit: int
    offset: int


@dataclass(frozen=True)
class SourceChunkPage:
    document_id: str
    items: list[dict[str, Any]]
    total: int
    limit: int
    offset: int


class SourceClient:
    """Server-to-server client for protected source inspection."""

    def __init__(
        self,
        settings: UISettings,
        *,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._settings = settings
        self._transport = transport

    def list_sources(
        self,
        *,
        query: str | None = None,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> SourceListPage:
        params: dict[str, str | int] = {"limit": limit, "offset": offset}
        if query:
            params["query"] = query
        if status:
            params["status"] = status

        payload = self._get("/api/sources/", params=params)
        items = payload.get("items")
        total = payload.get("total")
        returned_limit = payload.get("limit")
        returned_offset = payload.get("offset")

        if (
            not isinstance(items, list)
            or not isinstance(total, int)
            or not isinstance(returned_limit, int)
            or not isinstance(returned_offset, int)
            or any(not isinstance(item, dict) for item in items)
        ):
            raise _invalid_payload_error()

        return SourceListPage(
            items=items,
            total=total,
            limit=returned_limit,
            offset=returned_offset,
        )

    def get_stats(self) -> dict[str, Any]:
        return self._get("/api/sources/stats")

    def get_source(self, source_id: str) -> dict[str, Any]:
        return self._get(f"/api/sources/{source_id}")

    def get_chunks(
        self,
        source_id: str,
        *,
        limit: int = 10,
        offset: int = 0,
    ) -> SourceChunkPage:
        payload = self._get(
            f"/api/sources/{source_id}/chunks",
            params={"limit": limit, "offset": offset},
        )
        document_id = payload.get("document_id")
        items = payload.get("items")
        total = payload.get("total")
        returned_limit = payload.get("limit")
        returned_offset = payload.get("offset")

        if (
            not isinstance(document_id, str)
            or not isinstance(items, list)
            or not isinstance(total, int)
            or not isinstance(returned_limit, int)
            or not isinstance(returned_offset, int)
            or any(not isinstance(item, dict) for item in items)
        ):
            raise _invalid_payload_error()

        return SourceChunkPage(
            document_id=document_id,
            items=items,
            total=total,
            limit=returned_limit,
            offset=returned_offset,
        )

    def _get(
        self,
        path: str,
        *,
        params: dict[str, str | int] | None = None,
    ) -> dict[str, Any]:
        key = self._settings.developer_ui_access_key
        if key is None or not key.strip():
            raise SourceServiceError(
                code="not_configured",
                user_message=(
                    "The developer source workspace is not configured. "
                    "Set the developer access key and restart the interface."
                ),
            )

        headers = {
            DEVELOPER_KEY_HEADER: key,
            "Accept": "application/json",
            "User-Agent": "pliris-developer-ui/0.1",
        }

        try:
            with httpx.Client(
                timeout=self._settings.api_timeout_seconds,
                transport=self._transport,
            ) as client:
                response = client.get(
                    f"{self._settings.api_url}{path}",
                    headers=headers,
                    params=params,
                )
        except httpx.TimeoutException as exc:
            raise SourceServiceError(
                code="timeout",
                user_message=(
                    "Source inspection is taking longer than expected. Please retry shortly."
                ),
            ) from exc
        except httpx.RequestError as exc:
            raise SourceServiceError(
                code="unavailable",
                user_message=("The source-inspection service is temporarily unavailable."),
            ) from exc

        if response.status_code != 200:
            raise _service_error_from_response(response)

        try:
            payload = response.json()
        except ValueError as exc:
            raise _invalid_payload_error() from exc

        if not isinstance(payload, dict):
            raise _invalid_payload_error()

        _assert_safe_payload(payload)
        return payload


def _assert_safe_payload(value: Any) -> None:
    if isinstance(value, dict):
        if _FORBIDDEN_RESPONSE_FIELDS.intersection(value):
            raise _invalid_payload_error()
        for item in value.values():
            _assert_safe_payload(item)
    elif isinstance(value, list):
        for item in value:
            _assert_safe_payload(item)


def _service_error_from_response(
    response: httpx.Response,
) -> SourceServiceError:
    status_code = response.status_code
    if status_code in {401, 403}:
        code = "not_authorized"
        message = "The source workspace could not authenticate with the developer API."
    elif status_code == 404:
        code = "not_found"
        message = "That knowledge-base source could not be found."
    elif status_code == 422:
        code = "validation"
        message = "The source filter or page request was not valid."
    elif status_code in {502, 503, 504}:
        code = "unavailable"
        message = "The source-inspection service is temporarily unavailable."
    elif status_code >= 500:
        code = "server_error"
        message = "The source-inspection service encountered a temporary problem."
    else:
        code = "request_failed"
        message = "The source-inspection request could not be completed."

    return SourceServiceError(
        code=code,
        user_message=message,
        status_code=status_code,
    )


def _invalid_payload_error() -> SourceServiceError:
    return SourceServiceError(
        code="invalid_response",
        user_message=("The source-inspection service returned an incomplete response."),
        status_code=200,
    )
