from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class DocumentManifestEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document_id: str = Field(min_length=1, pattern=r"^[a-z0-9][a-z0-9-]*$")
    title: str = Field(min_length=1)
    source_filename: str = Field(min_length=1)
    author: str | None = None
    edition: str | None = None
    publication_year: int | None = Field(default=None, ge=1000, le=2100)
    source_type: str = "book"
    access: Literal["private", "public"] = "private"
    include_in_public_repository: bool = False
    enabled: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_private_sources(self) -> DocumentManifestEntry:
        if self.access == "private" and self.include_in_public_repository:
            raise ValueError(
                "Private documents cannot be marked for inclusion in the public repository."
            )
        return self


class CorpusManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: int = Field(default=1, ge=1)
    documents: list[DocumentManifestEntry]

    @model_validator(mode="after")
    def validate_unique_document_ids(self) -> CorpusManifest:
        ids = [document.document_id for document in self.documents]
        duplicates = sorted({document_id for document_id in ids if ids.count(document_id) > 1})
        if duplicates:
            raise ValueError(f"Duplicate document IDs: {duplicates}")
        return self


@dataclass(slots=True)
class ExtractedPage:
    page_number: int
    text: str
    character_count: int
    warnings: list[str] = field(default_factory=list)


@dataclass(slots=True)
class ExtractedDocument:
    path: Path
    page_count: int
    pages: list[ExtractedPage]
    pdf_metadata: dict[str, Any]
    warnings: list[str] = field(default_factory=list)


@dataclass(slots=True)
class DocumentChunk:
    chunk_index: int
    content: str
    page_start: int
    page_end: int
    chapter: str | None
    section: str | None
    heading_path: list[str]
    token_count: int
    content_hash: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class IngestionSummary:
    document_id: str
    database_document_id: str | None
    status: Literal["dry_run", "skipped", "completed", "failed"]
    source_path: str
    storage_path: str | None
    page_count: int
    chunk_count: int
    estimated_embedding_tokens: int
    warnings: list[str] = field(default_factory=list)
