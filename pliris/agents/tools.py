"""Tools and utilities for agents."""

import logging

logger = logging.getLogger(__name__)


class ToolRegistry:
    """Registry for agent tools."""

    def __init__(self):
        self._tools = {}

    def register(self, name: str, tool_func):
        """Register a tool."""
        self._tools[name] = tool_func
        logger.info(f"Registered tool: {name}")

    def get(self, name: str):
        """Get a tool by name."""
        return self._tools.get(name)

    def list_tools(self) -> list[str]:
        """List all registered tools."""
        return list(self._tools.keys())


# Example tools
async def search_documents(query: str, top_k: int = 5) -> list[dict]:
    """Search documents tool."""
    from pliris.retrieval.hybrid_search import HybridSearch

    search = HybridSearch()
    return await search.search(query, top_k)


async def get_document_metadata(document_id: str) -> dict:
    """Get document metadata tool."""
    from pliris.database.repositories.documents import DocumentRepository

    repo = DocumentRepository()
    return await repo.get_by_id(document_id)


async def calculate_financial_metrics(data: dict) -> dict:
    """Calculate financial metrics tool."""
    # Placeholder for financial calculations
    return {"metrics": {}, "status": "calculated"}
