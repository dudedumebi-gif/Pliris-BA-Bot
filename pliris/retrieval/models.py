from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class RetrievedChunk:
    """Normalized chunk returned by production retrieval."""

    rank: int
    chunk_id: str
    text: str
    title: str
    source: str
    page_start: int | None
    page_end: int | None
    score: float
    document_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def page_label(self) -> str:
        if self.page_start is None and self.page_end is None:
            return "Not specified"
        if self.page_start is None:
            return str(self.page_end)
        if self.page_end is None or self.page_end == self.page_start:
            return str(self.page_start)
        return f"{self.page_start}-{self.page_end}"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
