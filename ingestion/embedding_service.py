from __future__ import annotations

from dataclasses import dataclass

from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

from pliris.config.settings import get_settings


@dataclass(slots=True)
class EmbeddingBatchResult:
    embeddings: list[list[float]]
    input_tokens: int


class EmbeddingService:
    """Generate and validate OpenAI embeddings in bounded batches."""

    def __init__(self, client: OpenAI | None = None) -> None:
        self.settings = get_settings()
        self.client = client or OpenAI(api_key=self.settings.openai_api_key.get_secret_value())

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        reraise=True,
    )
    def _embed_batch(self, texts: list[str]) -> EmbeddingBatchResult:
        response = self.client.embeddings.create(
            model=self.settings.openai_embedding_model,
            input=texts,
            dimensions=self.settings.openai_embedding_dimensions,
        )

        ordered = sorted(response.data, key=lambda item: item.index)
        embeddings = [item.embedding for item in ordered]

        for embedding in embeddings:
            if len(embedding) != self.settings.openai_embedding_dimensions:
                raise ValueError(
                    "Embedding dimension mismatch: "
                    f"expected {self.settings.openai_embedding_dimensions}, "
                    f"received {len(embedding)}."
                )

        input_tokens = int(getattr(response.usage, "prompt_tokens", 0) or 0)
        return EmbeddingBatchResult(
            embeddings=embeddings,
            input_tokens=input_tokens,
        )

    def embed_texts(
        self,
        texts: list[str],
        *,
        batch_size: int = 64,
    ) -> EmbeddingBatchResult:
        if not texts:
            return EmbeddingBatchResult(embeddings=[], input_tokens=0)
        if batch_size <= 0:
            raise ValueError("batch_size must be greater than zero.")

        all_embeddings: list[list[float]] = []
        total_tokens = 0

        for start in range(0, len(texts), batch_size):
            result = self._embed_batch(texts[start : start + batch_size])
            all_embeddings.extend(result.embeddings)
            total_tokens += result.input_tokens

        return EmbeddingBatchResult(
            embeddings=all_embeddings,
            input_tokens=total_tokens,
        )
