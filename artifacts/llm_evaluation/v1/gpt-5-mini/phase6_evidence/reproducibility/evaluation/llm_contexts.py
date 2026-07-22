from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import Field

from evaluation.llm_contract import (
    ContextStrategy,
    EvaluationCase,
    EvaluationContract,
    StrictModel,
    contract_fingerprint,
)
from pliris.generation.context_assembler import (
    AssembledContext,
    ContextAssembler,
    ContextSource,
)
from pliris.retrieval.models import RetrievedChunk


class ContextFreezeError(RuntimeError):
    """Raised when a frozen evaluation context is incomplete or invalid."""


class FrozenChunk(StrictModel):
    rank: int = Field(ge=1)
    chunk_id: str = Field(min_length=1)
    text: str = Field(min_length=1)
    title: str = Field(min_length=1)
    source: str = Field(min_length=1)
    page_start: int | None = Field(default=None, ge=1)
    page_end: int | None = Field(default=None, ge=1)
    score: float
    document_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    def to_retrieved_chunk(self) -> RetrievedChunk:
        return RetrievedChunk(
            rank=self.rank,
            chunk_id=self.chunk_id,
            text=self.text,
            title=self.title,
            source=self.source,
            page_start=self.page_start,
            page_end=self.page_end,
            score=self.score,
            document_id=self.document_id,
            metadata=dict(self.metadata),
        )


class FrozenSource(StrictModel):
    citation_id: str = Field(min_length=1)
    chunk_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    source: str = Field(min_length=1)
    page_start: int | None = Field(default=None, ge=1)
    page_end: int | None = Field(default=None, ge=1)
    page_label: str = Field(min_length=1)
    score: float
    rank: int = Field(ge=1)
    document_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    def to_context_source(self) -> ContextSource:
        return ContextSource(
            citation_id=self.citation_id,
            chunk_id=self.chunk_id,
            title=self.title,
            source=self.source,
            page_start=self.page_start,
            page_end=self.page_end,
            page_label=self.page_label,
            score=self.score,
            rank=self.rank,
            document_id=self.document_id,
            metadata=dict(self.metadata),
        )


class ContextQuality(StrictModel):
    page_overlap_count: int = Field(ge=0)
    matched_term_group_count: int = Field(ge=0)
    minimum_term_groups: int = Field(ge=0)
    passed: bool


class FrozenContextRecord(StrictModel):
    record_type: Literal["context"] = "context"
    contract_fingerprint: str = Field(min_length=64, max_length=64)
    context_fingerprint: str = Field(min_length=64, max_length=64)
    case_id: str = Field(min_length=1)
    question: str = Field(min_length=1)
    request_mode: str = Field(min_length=1)
    context_strategy: ContextStrategy
    retrieval_query: str | None = None
    document_id: str | None = None
    chunks: tuple[FrozenChunk, ...]
    context_text: str = Field(min_length=1)
    sources: tuple[FrozenSource, ...]
    omitted_count: int = Field(ge=0)
    character_count: int = Field(ge=1)
    truncated: bool
    quality: ContextQuality

    def to_assembled_context(self) -> AssembledContext:
        return AssembledContext(
            text=self.context_text,
            sources=tuple(source.to_context_source() for source in self.sources),
            omitted_count=self.omitted_count,
            character_count=self.character_count,
            truncated=self.truncated,
        )

    def to_retrieved_chunks(self) -> list[RetrievedChunk]:
        return [chunk.to_retrieved_chunk() for chunk in self.chunks]


class FrozenContextManifest(StrictModel):
    record_type: Literal["manifest"] = "manifest"
    contract_fingerprint: str = Field(min_length=64, max_length=64)
    benchmark_version: int = Field(ge=1)
    case_count: int = Field(ge=1)
    top_k: int = Field(ge=1)
    embedding_input_tokens: int = Field(ge=0)
    embedding_input_price_per_million: float = Field(ge=0)
    embedding_estimated_cost_usd: float = Field(ge=0)
    created_at_utc: str = Field(min_length=1)


@dataclass(frozen=True, slots=True)
class FrozenContextBundle:
    manifest: FrozenContextManifest
    records: tuple[FrozenContextRecord, ...]

    def by_case_id(self) -> dict[str, FrozenContextRecord]:
        return {record.case_id: record for record in self.records}


class MeteredEmbeddingService:
    """Accumulate actual embedding input tokens without changing production retrieval."""

    def __init__(self, delegate: Any) -> None:
        self.delegate = delegate
        self.input_tokens = 0

    def embed_texts(self, texts: list[str], **kwargs: Any) -> Any:
        result = self.delegate.embed_texts(texts, **kwargs)
        self.input_tokens += int(getattr(result, "input_tokens", 0) or 0)
        return result


def _canonical_hash(payload: dict[str, Any]) -> str:
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def context_fingerprint(record: FrozenContextRecord) -> str:
    payload = record.model_dump(
        mode="json",
        exclude={"context_fingerprint"},
    )
    return _canonical_hash(payload)


def _page_overlaps(
    page_start: int | None,
    page_end: int | None,
    expected_start: int,
    expected_end: int,
) -> bool:
    if page_start is None and page_end is None:
        return False
    normalized_start = page_start if page_start is not None else page_end
    normalized_end = page_end if page_end is not None else page_start
    if normalized_start is None or normalized_end is None:
        return False
    return normalized_start <= expected_end and normalized_end >= expected_start


def _matched_term_groups(
    text: str,
    required_term_groups: tuple[tuple[str, ...], ...],
) -> int:
    normalized = " ".join(text.lower().split())
    return sum(
        1 for group in required_term_groups if any(term.lower() in normalized for term in group)
    )


def assess_context_quality(
    case: EvaluationCase,
    chunks: list[RetrievedChunk],
    context: AssembledContext,
) -> ContextQuality:
    page_overlap_count = sum(
        1
        for chunk in chunks
        if any(
            _page_overlaps(
                chunk.page_start,
                chunk.page_end,
                expected.start,
                expected.end,
            )
            for expected in case.expected_page_ranges
        )
    )
    matched_term_group_count = _matched_term_groups(
        context.text,
        case.required_term_groups,
    )

    if case.context_strategy is ContextStrategy.RETRIEVAL:
        passed = (
            bool(chunks)
            and bool(context.sources)
            and page_overlap_count >= 1
            and matched_term_group_count >= case.minimum_term_groups
        )
    elif case.context_strategy is ContextStrategy.SYNTHETIC:
        passed = bool(chunks) and bool(context.sources)
    else:
        passed = not chunks and not context.sources

    return ContextQuality(
        page_overlap_count=page_overlap_count,
        matched_term_group_count=matched_term_group_count,
        minimum_term_groups=case.minimum_term_groups,
        passed=passed,
    )


def _synthetic_chunks(case: EvaluationCase) -> list[RetrievedChunk]:
    return [
        RetrievedChunk(
            rank=index,
            chunk_id=chunk.chunk_id,
            text=chunk.text,
            title=chunk.title,
            source=chunk.source,
            page_start=chunk.page_start,
            page_end=chunk.page_end,
            score=1.0,
            document_id=None,
            metadata={
                "evaluation_fixture": True,
                "evaluation_case_id": case.id,
            },
        )
        for index, chunk in enumerate(case.synthetic_chunks, start=1)
    ]


def _freeze_record(
    *,
    fingerprint: str,
    case: EvaluationCase,
    chunks: list[RetrievedChunk],
    context: AssembledContext,
    quality: ContextQuality,
) -> FrozenContextRecord:
    base = FrozenContextRecord(
        contract_fingerprint=fingerprint,
        context_fingerprint="0" * 64,
        case_id=case.id,
        question=case.question,
        request_mode=case.request_mode.value,
        context_strategy=case.context_strategy,
        retrieval_query=case.retrieval_query,
        document_id=case.document_id,
        chunks=tuple(FrozenChunk.model_validate(chunk.to_dict()) for chunk in chunks),
        context_text=context.text,
        sources=tuple(FrozenSource.model_validate(source.to_dict()) for source in context.sources),
        omitted_count=context.omitted_count,
        character_count=context.character_count,
        truncated=context.truncated,
        quality=quality,
    )
    return base.model_copy(update={"context_fingerprint": context_fingerprint(base)})


async def freeze_contexts(
    contract: EvaluationContract,
    *,
    retriever: Any,
    assembler: ContextAssembler | None = None,
    embedding_usage_provider: Callable[[], int] | None = None,
    embedding_price_per_million: float = 0.0,
) -> FrozenContextBundle:
    if embedding_price_per_million < 0:
        raise ValueError("embedding_price_per_million cannot be negative")

    context_assembler = assembler or ContextAssembler(max_chunks=contract.config.retrieval.top_k)
    fingerprint = contract_fingerprint(contract)
    records: list[FrozenContextRecord] = []

    for case in contract.benchmark.cases:
        if case.context_strategy is ContextStrategy.RETRIEVAL:
            chunks = await retriever.search(
                case.retrieval_query or case.question,
                top_k=contract.config.retrieval.top_k,
                document_id=case.document_id,
            )
        elif case.context_strategy is ContextStrategy.SYNTHETIC:
            chunks = _synthetic_chunks(case)
        else:
            chunks = []

        context = context_assembler.assemble(chunks)
        quality = assess_context_quality(case, chunks, context)
        if not quality.passed:
            raise ContextFreezeError(
                "Context quality gate failed for "
                f"{case.id!r}: page_overlap_count="
                f"{quality.page_overlap_count}, matched_term_group_count="
                f"{quality.matched_term_group_count}, minimum_term_groups="
                f"{quality.minimum_term_groups}."
            )

        records.append(
            _freeze_record(
                fingerprint=fingerprint,
                case=case,
                chunks=chunks,
                context=context,
                quality=quality,
            )
        )

    embedding_input_tokens = (
        int(embedding_usage_provider() or 0) if embedding_usage_provider is not None else 0
    )
    embedding_estimated_cost_usd = embedding_input_tokens / 1_000_000 * embedding_price_per_million
    manifest = FrozenContextManifest(
        contract_fingerprint=fingerprint,
        benchmark_version=contract.benchmark.version,
        case_count=len(records),
        top_k=contract.config.retrieval.top_k,
        embedding_input_tokens=embedding_input_tokens,
        embedding_input_price_per_million=(embedding_price_per_million),
        embedding_estimated_cost_usd=round(
            embedding_estimated_cost_usd,
            8,
        ),
        created_at_utc=datetime.now(UTC).isoformat(),
    )
    return FrozenContextBundle(manifest=manifest, records=tuple(records))


def write_frozen_contexts(
    path: Path,
    bundle: FrozenContextBundle,
) -> None:
    destination = path.resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".tmp")

    with temporary.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(
            json.dumps(
                bundle.manifest.model_dump(mode="json"),
                ensure_ascii=False,
                sort_keys=True,
            )
            + "\n"
        )
        for record in bundle.records:
            handle.write(
                json.dumps(
                    record.model_dump(mode="json"),
                    ensure_ascii=False,
                    sort_keys=True,
                )
                + "\n"
            )
        handle.flush()
        os.fsync(handle.fileno())

    temporary.replace(destination)


def load_frozen_contexts(
    path: Path,
    contract: EvaluationContract,
) -> FrozenContextBundle:
    source = path.resolve()
    try:
        lines = [line for line in source.read_text(encoding="utf-8").splitlines() if line.strip()]
    except FileNotFoundError as exc:
        raise ContextFreezeError(f"Frozen context file not found: {source}") from exc

    if len(lines) < 2:
        raise ContextFreezeError(
            "Frozen context file must contain one manifest and context records."
        )

    try:
        manifest = FrozenContextManifest.model_validate_json(lines[0])
        records = tuple(FrozenContextRecord.model_validate_json(line) for line in lines[1:])
    except Exception as exc:
        raise ContextFreezeError(f"Frozen context file is invalid: {source}") from exc

    expected_fingerprint = contract_fingerprint(contract)
    if manifest.contract_fingerprint != expected_fingerprint:
        raise ContextFreezeError("Frozen context manifest does not match the active contract.")

    expected_ids = {case.id for case in contract.benchmark.cases}
    actual_ids = {record.case_id for record in records}
    if len(records) != len(actual_ids):
        raise ContextFreezeError("Frozen context case ids must be unique.")
    if actual_ids != expected_ids:
        raise ContextFreezeError("Frozen context cases do not exactly match the benchmark.")
    if manifest.case_count != len(records):
        raise ContextFreezeError("Frozen context manifest case_count does not match its records.")

    for record in records:
        if record.contract_fingerprint != expected_fingerprint:
            raise ContextFreezeError(
                f"Context {record.case_id!r} has a mismatched contract fingerprint."
            )
        if context_fingerprint(record) != record.context_fingerprint:
            raise ContextFreezeError(f"Context {record.case_id!r} failed fingerprint validation.")
        if not record.quality.passed:
            raise ContextFreezeError(f"Context {record.case_id!r} did not pass its quality gate.")

    return FrozenContextBundle(manifest=manifest, records=records)
