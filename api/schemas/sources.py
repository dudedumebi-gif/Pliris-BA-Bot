from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

SourceStatus = Literal["pending", "processing", "ready", "failed", "archived"]


class SourceSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    manifest_id: str | None = None
    title: str
    source_filename: str
    author: str | None = None
    source_type: str
    access: str
    status: SourceStatus
    page_count: int | None = Field(default=None, ge=1)
    chunk_count: int = Field(ge=0)
    total_tokens: int = Field(ge=0)
    last_ingested_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class SourceDetail(SourceSummary):
    edition: str | None = None
    publication_year: int | None = None
    mime_type: str
    checksum_sha256: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    has_ingestion_error: bool = False


class SourceListResponse(BaseModel):
    items: list[SourceSummary]
    total: int = Field(ge=0)
    limit: int = Field(ge=1)
    offset: int = Field(ge=0)


class SourceStats(BaseModel):
    total_documents: int = Field(ge=0)
    total_chunks: int = Field(ge=0)
    total_pages: int = Field(ge=0)
    total_tokens: int = Field(ge=0)
    ready_documents: int = Field(ge=0)
    pending_documents: int = Field(ge=0)
    processing_documents: int = Field(ge=0)
    failed_documents: int = Field(ge=0)
    archived_documents: int = Field(ge=0)
    last_ingested_at: datetime | None = None


class SourceChunk(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    chunk_index: int = Field(ge=0)
    content: str
    page_start: int | None = Field(default=None, ge=1)
    page_end: int | None = Field(default=None, ge=1)
    chapter: str | None = None
    section: str | None = None
    heading_path: list[str] = Field(default_factory=list)
    token_count: int | None = Field(default=None, ge=1)
    content_hash: str
    embedding_model: str
    created_at: datetime
    updated_at: datetime


class SourceChunkListResponse(BaseModel):
    document_id: UUID
    items: list[SourceChunk]
    total: int = Field(ge=0)
    limit: int = Field(ge=1)
    offset: int = Field(ge=0)
