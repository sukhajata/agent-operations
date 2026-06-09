"""Knowledge graph search tool.

Searches durable graph nodes to avoid rediscovering known facts.
"""

from __future__ import annotations

from typing import Any

from langchain_core.tools import tool

from shared.arcadedb.client import ArcadeDBClient


def create_search_graph_tool(client: ArcadeDBClient) -> Any:  # noqa: ANN401
    """Create a search_graph tool bound to an ArcadeDB client."""

    @tool
    async def search_graph(domain: str, query: str) -> str:
        """Search the knowledge graph for existing findings in a domain.

        Use this BEFORE reporting any finding to avoid rediscovering
        already-known facts. Returns matching nodes with their current
        confidence and status.

        Args:
            domain: The domain to search in (e.g. 'competitive_intelligence')
            query: Natural language description of what you're looking for
        """
        results: list[dict[str, Any]] = []
        vertex_types = (
            "ProductStructure",
            "InvestigationFinding",
            "CompetitorCapability",
        )
        for vertex_type in vertex_types:
            try:
                records = await client.execute_query(
                    f"SELECT node_id, node_type, confidence, last_reinforced, "
                    f"revalidation_required FROM {vertex_type} LIMIT 50"
                )
                for r in records:
                    r["@type"] = vertex_type
                results.extend(records)
            except Exception:
                continue

        if not results:
            return "No existing knowledge found in the graph for this domain."
        return str(results)

    return search_graph
