import logging

from openai import AsyncOpenAI

from pliris.config.settings import settings

logger = logging.getLogger(__name__)


class OpenAIClient:
    """Client for OpenAI API interactions."""

    def __init__(self):
        self.client = AsyncOpenAI(api_key=settings.openai_api_key.get_secret_value())

    async def generate(
        self,
        prompt: str,
        model: str | None = None,
        max_tokens: int = 1000,
        temperature: float = 0.7,
    ) -> str:
        """
        Generate text using OpenAI.

        Args:
            prompt: Input prompt
            model: Model to use (defaults to settings)
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature

        Returns:
            Generated text
        """
        try:
            model = model or settings.openai_model

            response = await self.client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "You are a helpful business analyst assistant."},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=max_tokens,
                temperature=temperature,
            )

            return response.choices[0].message.content

        except Exception as e:
            logger.error(f"Error generating text: {e}", exc_info=True)
            raise

    async def get_embedding(self, text: str) -> list[float]:
        """
        Get embedding for text.

        Args:
            text: Input text

        Returns:
            Embedding vector
        """
        try:
            response = await self.client.embeddings.create(
                model=settings.openai_embedding_model, input=text
            )

            return response.data[0].embedding

        except Exception as e:
            logger.error(f"Error getting embedding: {e}", exc_info=True)
            raise

    async def check_connection(self) -> bool:
        """Check if OpenAI API is accessible."""
        try:
            await self.get_embedding("test")
            return True
        except Exception as e:
            logger.error(f"OpenAI connection check failed: {e}")
            return False
