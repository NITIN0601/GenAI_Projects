"""
Vector store implementations.

Multiple vector database backends.
"""

from src.infrastructure.vectordb.stores.chromadb_store import VectorStore, get_vector_store
from src.infrastructure.vectordb.stores.faiss_store import FAISSVectorStore, get_faiss_store
from src.infrastructure.vectordb.stores.redis_store import RedisVectorStore, get_redis_store

# Alias for consistency
ChromaDBStore = VectorStore

__all__ = [
    # ChromaDB
    'VectorStore',
    'ChromaDBStore',  # Alias
    'get_vector_store',
    # FAISS
    'FAISSVectorStore',
    'get_faiss_store',
    # Redis
    'RedisVectorStore',
    'get_redis_store',
]
