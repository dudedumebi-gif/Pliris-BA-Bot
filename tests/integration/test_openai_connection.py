"""Integration tests for OpenAI connection."""

import pytest

from pliris.generation.openai_client import OpenAIClient

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_openai_client():
    """Test OpenAI client initialization."""
    client = OpenAIClient()

    assert client is not None
    assert client.client is not None


@pytest.mark.asyncio
async def test_openai_generate():
    """Test OpenAI text generation."""
    client = OpenAIClient()

    response = await client.generate(
        prompt="Say 'Hello, World!'", model="gpt-4o-mini", max_tokens=20
    )

    assert response is not None
    assert isinstance(response, str)
    assert len(response) > 0


@pytest.mark.asyncio
async def test_openai_embedding():
    """Test OpenAI embedding generation."""
    client = OpenAIClient()

    embedding = await client.get_embedding("test text")

    assert embedding is not None
    assert isinstance(embedding, list)
    assert len(embedding) > 0
    assert all(isinstance(x, float) for x in embedding)
