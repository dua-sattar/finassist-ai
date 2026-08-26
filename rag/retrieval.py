"""Build and query the FinAssist AI knowledge-base vector index."""

import logging
from dataclasses import dataclass

from rag.ingestion import load_and_chunk
from rag.vector_store import get_client, get_collection, reset_collection

logger = logging.getLogger(__name__)


@dataclass
class RetrievedChunk:
    text: str
    source: str
    distance: float


def build_index() -> int:
    """(Re)build the vector store from knowledge_base/*.md. Idempotent: clears
    and recreates the collection each time, since the KB is small. Returns the
    number of chunks indexed."""
    client = get_client()
    collection = reset_collection(client)

    chunks = load_and_chunk()
    if not chunks:
        logger.warning("No knowledge base chunks found to index")
        return 0

    collection.add(
        ids=[c.id for c in chunks],
        documents=[c.text for c in chunks],
        metadatas=[{"source": c.source} for c in chunks],
    )
    return len(chunks)


def retrieve(query: str, k: int = 4) -> list[RetrievedChunk]:
    """Retrieve the top-k most relevant knowledge-base chunks for a query.

    Returns an empty list (rather than raising) on retrieval failure -- e.g. an
    empty/uninitialized index or an OpenAI embedding-API error -- so callers
    can show a friendly "nothing found" message instead of crashing.
    """
    try:
        collection = get_collection()
        results = collection.query(query_texts=[query], n_results=k)
    except Exception as exc:
        logger.warning("RAG retrieval failed for query %r: %s", query, exc)
        return []

    documents = results.get("documents") or [[]]
    metadatas = results.get("metadatas") or [[]]
    distances = results.get("distances") or [[]]

    return [
        RetrievedChunk(text=text, source=meta.get("source", "unknown"), distance=distance)
        for text, meta, distance in zip(documents[0], metadatas[0], distances[0])
    ]
