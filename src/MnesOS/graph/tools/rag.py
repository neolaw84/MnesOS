"""
Director Batch RAG Tool for MnesOS.

Provides a batched lore retrieval interface to optimize cost and performance
by forcing the LLM to gather all queries simultaneously instead of making
sequential tool calls.

Aligned with docs/to-do-260507.md Phase 2 [MnesOS-260507-07].
"""

from pydantic import BaseModel, Field
from typing import List, Dict


class MultiLoreLookupInput(BaseModel):
    """Input schema for batched lore retrieval."""

    queries: List[str] = Field(
        description="A list of distinct search queries to retrieve relevant world lore simultaneously."
    )


class MultiLoreLookupOutput(BaseModel):
    """Output schema for batched lore retrieval."""

    results: Dict[str, str] = Field(
        description="Dictionary mapping each original query to its retrieved context snippet."
    )
