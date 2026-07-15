"""Integration tests for hybrid search."""

import pytest

pytestmark = pytest.mark.integration
from pliris.retrieval.hybrid_search import HybridSearch


@pytest.mark.asyncio
async def test_hybrid_search():
    """Test hybrid search functionality."""
    search = HybridSearch()

    results = await search.search(query="test query", top_k=5)

    assert isinstance(results, list)
    # Results may be empty if no documents are indexed
    assert all(isinstance(r, dict) for r in results)


@pytest.mark.asyncio
async def test_hybrid_search_with_filters():
    """Test hybrid search with filters."""
    search = HybridSearch()

    results = await search.search(query="test query", top_k=5, filters={"source": "test"})

    assert isinstance(results, list)
