"""search_knowledge_base tool -- retrieves relevant FinAssist AI policy
context from the RAG index (rag/retrieval.py)."""

import logging

from pydantic import BaseModel

from rag.retrieval import retrieve
from tools.common import log_action

logger = logging.getLogger(__name__)


class KnowledgeChunk(BaseModel):
    text: str
    source: str
    distance: float


class SearchKnowledgeBaseResult(BaseModel):
    success: bool
    query: str
    chunks: list[KnowledgeChunk] = []
    error: str | None = None


def search_knowledge_base(query: str, k: int = 4) -> SearchKnowledgeBaseResult:
    """Search the FinAssist AI knowledge base for policy information relevant to `query`."""
    try:
        chunks = retrieve(query, k=k)
        result = SearchKnowledgeBaseResult(
            success=True,
            query=query,
            chunks=[KnowledgeChunk(text=c.text, source=c.source, distance=c.distance) for c in chunks],
        )
        log_action("search_knowledge_base", f"query={query!r} k={k}", f"{len(chunks)} chunks retrieved")
        return result
    except Exception as exc:
        logger.warning("search_knowledge_base failed for %r: %s", query, exc)
        log_action("search_knowledge_base", f"query={query!r} k={k}", str(exc), status="error")
        return SearchKnowledgeBaseResult(success=False, query=query, error=str(exc))
