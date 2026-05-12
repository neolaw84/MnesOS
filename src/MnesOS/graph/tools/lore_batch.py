"""
Director Batch RAG Tool for MnesOS.

Implements the ``multi_lore_lookup`` LangGraph tool that lets the Director
retrieve world lore for *multiple* queries in a single batch call, replacing
the old per-turn pre-node injection pattern.

Aligned with ``docs/design/0006-stateless-phase-2.md`` §4 (Batch RAG Tooling /
[MnesOS-260507-07]).

Classes
-------
MultiLoreLookupArgs
    Pydantic model for the tool's public arguments.
LoreSearchService
    ABC: ``search_batch(queries, k) → str``.
VectorLoreSearchService
    Concrete adapter wrapping :class:`~MnesOS.context.VectorLoreStore`.

Functions
---------
build_multi_lore_lookup_tool(svc)
    Factory that returns a compiled LangGraph tool wired to *svc*.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List

from langchain_core.messages import ToolMessage
from langchain_core.tools import tool
from langgraph.types import Command
from pydantic import BaseModel, Field

from ...context import VectorLoreStore


# ---------------------------------------------------------------------------
# MultiLoreLookupArgs
# ---------------------------------------------------------------------------


class MultiLoreLookupArgs(BaseModel):
    """Public arguments for the ``multi_lore_lookup`` batch RAG tool."""

    queries: List[str] = Field(
        ...,
        description=(
            "Ordered list of lore lookup questions to batch into a single "
            "retrieval call.  Pass ALL open questions at once rather than "
            "making multiple separate calls."
        ),
    )


# ---------------------------------------------------------------------------
# LoreSearchService (ABC)
# ---------------------------------------------------------------------------


class LoreSearchService(ABC):
    """Abstract interface for batch lore retrieval."""

    @abstractmethod
    def search_batch(self, queries: List[str], k: int = 3) -> str:
        """Search for lore matching *queries* and return combined text.

        Parameters
        ----------
        queries:
            One or more natural-language search questions.
        k:
            Number of top chunks to retrieve per query (default: 3).

        Returns
        -------
        str
            Deduplicated lore chunks joined by ``\\n\\n---\\n\\n``,
            or an empty string when no relevant lore is found.
        """


# ---------------------------------------------------------------------------
# VectorLoreSearchService — concrete adapter
# ---------------------------------------------------------------------------


class VectorLoreSearchService(LoreSearchService):
    """Concrete :class:`LoreSearchService` backed by :class:`~MnesOS.context.VectorLoreStore`.

    Deduplicates retrieved chunks across queries so that repeated or
    overlapping search terms do not inflate the context window.
    """

    def __init__(self, lore_content: str) -> None:
        self._lore_content = lore_content
        self._store: VectorLoreStore | None = (
            VectorLoreStore(lore_content) if lore_content and lore_content.strip() else None
        )

    @classmethod
    def from_file(cls, filepath: str) -> "VectorLoreSearchService":
        """Construct from a lore Markdown file.

        Raises
        ------
        FileNotFoundError
            If *filepath* does not exist.
        """
        with open(filepath, "r") as fh:
            return cls(fh.read())

    def search_batch(self, queries: List[str], k: int = 3) -> str:
        """Retrieve and deduplicate lore for all *queries* in a single pass."""
        if not queries or self._store is None:
            return ""

        seen: set[str] = set()
        chunks: List[str] = []

        for q in queries:
            raw = self._store.query(q, top_k=k)
            if not raw:
                continue
            for chunk in raw.split("\n\n---\n\n"):
                chunk = chunk.strip()
                if chunk and chunk not in seen:
                    seen.add(chunk)
                    chunks.append(chunk)

        return "\n\n---\n\n".join(chunks)


# ---------------------------------------------------------------------------
# build_multi_lore_lookup_tool factory
# ---------------------------------------------------------------------------


def build_multi_lore_lookup_tool(svc: LoreSearchService):
    """Factory that returns a ``multi_lore_lookup`` LangGraph tool.

    The tool calls ``svc.search_batch`` exactly *once* for all queries and
    writes the result to ``GameState["retrieved_lore"]``.  It also appends
    a :class:`~langchain_core.messages.ToolMessage` to ``agent_messages``
    so the Director LLM receives confirmation.

    Parameters
    ----------
    svc:
        Any :class:`LoreSearchService` implementation.

    Returns
    -------
    StructuredTool
        A compiled LangGraph tool named ``multi_lore_lookup``.
    """

    @tool
    def multi_lore_lookup(
        queries: List[str],
        tool_call_id: str = "",
        state: dict = None,  # noqa: ARG001
    ) -> Command:
        """Batch lore lookup: retrieve world knowledge for multiple queries in one call.

        Call this tool BEFORE resolving any mechanics or writing scene
        directives whenever you need background information about people,
        places, events, or items.  Pass ALL your open questions as a single
        list so that only one retrieval call is made per turn.
        """
        lore = svc.search_batch(queries)
        n = len(queries)
        summary = f"Lore retrieved ({n} quer{'y' if n == 1 else 'ies'})."
        return Command(
            update={
                "retrieved_lore": lore,
                "agent_messages": [
                    ToolMessage(content=summary, tool_call_id=tool_call_id)
                ],
            }
        )

    return multi_lore_lookup
