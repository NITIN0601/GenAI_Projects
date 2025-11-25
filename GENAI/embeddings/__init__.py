"""Embeddings package initialization."""

from .embedding_manager import EmbeddingManager, get_embedding_manager
from .vector_store import VectorStore, get_vector_store

__all__ = [
    'EmbeddingManager',
    'get_embedding_manager',
    'VectorStore',
    'get_vector_store'
]
