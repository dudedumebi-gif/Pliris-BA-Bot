from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any, Protocol

DEFAULT_RERANKER_MODEL = "cross-encoder/ms-marco-MiniLM-L6-v2"


class CrossEncoderLike(Protocol):
    def predict(
        self,
        sentences: Sequence[tuple[str, str]],
        *,
        batch_size: int,
        show_progress_bar: bool,
        convert_to_numpy: bool,
    ) -> Any: ...


ModelFactory = Callable[[], CrossEncoderLike]


@dataclass(frozen=True, slots=True)
class RerankerConfig:
    model_name: str = DEFAULT_RERANKER_MODEL
    batch_size: int = 16
    max_length: int = 512
    device: str = "cpu"

    def __post_init__(self) -> None:
        if self.batch_size < 1:
            raise ValueError("batch_size must be positive.")
        if self.max_length < 32:
            raise ValueError("max_length must be at least 32.")


class LocalCrossEncoderReranker:
    """
    Lazy local cross-encoder reranker.

    The model is not imported or loaded until the first rerank call. This keeps
    the normal evaluation and unit-test paths lightweight.
    """

    def __init__(
        self,
        config: RerankerConfig | None = None,
        *,
        model_factory: ModelFactory | None = None,
    ) -> None:
        self.config = config or RerankerConfig()
        self._model_factory = model_factory
        self._model: CrossEncoderLike | None = None

    def _default_model_factory(self) -> CrossEncoderLike:
        try:
            from sentence_transformers import CrossEncoder
        except ImportError as exc:
            raise RuntimeError(
                "Local reranking requires sentence-transformers. "
                "Install it with: uv add sentence-transformers==5.6.0"
            ) from exc

        return CrossEncoder(
            self.config.model_name,
            max_length=self.config.max_length,
            device=self.config.device,
        )

    def _get_model(self) -> CrossEncoderLike:
        if self._model is None:
            factory = (
                self._model_factory
                if self._model_factory is not None
                else self._default_model_factory
            )
            self._model = factory()
        return self._model

    @staticmethod
    def _result_text(result: dict[str, Any]) -> str:
        for key in ("text", "content", "snippet", "page_content"):
            value = result.get(key)
            if value not in (None, ""):
                return str(value)

        metadata = result.get("metadata")
        if isinstance(metadata, dict):
            for key in ("text", "content", "snippet"):
                value = metadata.get(key)
                if value not in (None, ""):
                    return str(value)

        return ""

    def rerank(
        self,
        query: str,
        results: list[dict[str, Any]],
        *,
        top_k: int,
    ) -> list[dict[str, Any]]:
        if top_k < 1:
            raise ValueError("top_k must be positive.")
        if not results:
            return []

        pairs = [(query, self._result_text(result)) for result in results]
        scores = self._get_model().predict(
            pairs,
            batch_size=self.config.batch_size,
            show_progress_bar=False,
            convert_to_numpy=True,
        )
        score_values = [float(score) for score in scores]

        if len(score_values) != len(results):
            raise RuntimeError(
                "The reranker returned a different number of scores than candidate results."
            )

        scored: list[dict[str, Any]] = []
        for original_rank, (result, rerank_score) in enumerate(
            zip(results, score_values, strict=True),
            start=1,
        ):
            updated = dict(result)
            updated["retrieval_score"] = result.get("score")
            updated["rerank_score"] = rerank_score
            updated["original_rank"] = original_rank
            updated["score"] = rerank_score

            metadata = dict(result.get("metadata") or {})
            metadata.update(
                {
                    "retrieval_score": result.get("score"),
                    "rerank_score": rerank_score,
                    "original_rank": original_rank,
                    "reranker_model": self.config.model_name,
                }
            )
            updated["metadata"] = metadata
            scored.append(updated)

        scored.sort(
            key=lambda item: (
                float(item["rerank_score"]),
                -int(item["original_rank"]),
            ),
            reverse=True,
        )
        return scored[:top_k]
