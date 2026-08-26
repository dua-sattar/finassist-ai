"""Chroma persistent vector store setup for the FinAssist AI knowledge base."""

import logging
import os
from pathlib import Path

import chromadb
from dotenv import load_dotenv

from rag.embeddings import get_embedding_function

load_dotenv()

logger = logging.getLogger(__name__)

COLLECTION_NAME = "finassist_knowledge_base"


def get_client() -> chromadb.ClientAPI:
    persist_dir = os.getenv("VECTOR_DB_DIR", "./rag/vector_store")
    Path(persist_dir).mkdir(parents=True, exist_ok=True)
    return chromadb.PersistentClient(path=persist_dir)


def get_collection(client: chromadb.ClientAPI | None = None) -> chromadb.Collection:
    client = client or get_client()
    return client.get_or_create_collection(
        name=COLLECTION_NAME, embedding_function=get_embedding_function()
    )


def reset_collection(client: chromadb.ClientAPI | None = None) -> chromadb.Collection:
    """Delete and recreate the collection, for idempotent re-ingestion."""
    client = client or get_client()
    try:
        client.delete_collection(COLLECTION_NAME)
    except Exception as exc:
        logger.info("No existing collection to delete (%s)", exc)
    return get_collection(client)
