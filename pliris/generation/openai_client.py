from __future__ import annotations

import logging
from typing import TypeVar

from openai import AsyncOpenAI
from pydantic import BaseModel

from pliris.config.settings import settings

logger = logging.getLogger(__name__)

StructuredModelT = TypeVar("StructuredModelT", bound=BaseModel)


class OpenAIClient:
    """Client for OpenAI API interactions."""

    def __init__(self) -> None:
        self.client = AsyncOpenAI(api_key=settings.openai_api_key.get_secret_value())

    async def generate(
        self,
        prompt: str,
        model: str | None = None,
        max_tokens: int = 1000,
        temperature: float = 0.7,
    ) -> str:
        """Generate unstructured text using OpenAI."""

        try:
            selected_model = model or settings.openai_chat_model
            response = await self.client.chat.completions.create(
                model=selected_model,
                messages=[
                    {
                        "role": "system",
                        "content": ("You are a helpful business analyst assistant."),
                    },
                    {"role": "user", "content": prompt},
                ],
                max_tokens=max_tokens,
                temperature=temperature,
            )
            content = response.choices[0].message.content
            if content is None:
                raise RuntimeError("OpenAI returned no text content.")
            return content
        except Exception:
            logger.exception("Error generating text")
            raise

    async def generate_structured(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        response_model: type[StructuredModelT],
        model: str | None = None,
    ) -> StructuredModelT:
        """Generate a strict Pydantic-validated Responses API result."""

        try:
            response = await self.client.responses.parse(
                model=model or settings.openai_chat_model,
                input=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                text_format=response_model,
                store=False,
            )
            parsed = response.output_parsed
            if parsed is None:
                raise RuntimeError("OpenAI returned no parsed structured output.")
            return parsed
        except Exception:
            logger.exception("Error generating structured output")
            raise

    async def get_embedding(self, text: str) -> list[float]:
        """Get an embedding vector for text."""

        try:
            response = await self.client.embeddings.create(
                model=settings.openai_embedding_model,
                input=text,
            )
            return response.data[0].embedding
        except Exception:
            logger.exception("Error getting embedding")
            raise

    async def check_connection(self) -> bool:
        """Check if OpenAI API is accessible."""

        try:
            await self.get_embedding("test")
            return True
        except Exception:
            logger.exception("OpenAI connection check failed")
            return False
