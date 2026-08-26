"""Local embedding function used by the RAG vector store.

Uses a sentence-transformers model running on-device -- no API key, no cost,
no rate limit. The model (~80MB) downloads automatically from Hugging Face
on first use and is cached locally afterward.
"""

import os

from chromadb.utils import embedding_functions
from dotenv import load_dotenv

load_dotenv()


def get_embedding_function() -> embedding_functions.SentenceTransformerEmbeddingFunction:
    model_name = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
    return embedding_functions.SentenceTransformerEmbeddingFunction(model_name=model_name)
