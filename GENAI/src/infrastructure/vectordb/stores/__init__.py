"""
Vector store implementations.

Multiple vector database backends:
- ChromaDB (default, persistent)
- FAISS (high-performance)
- Redis Vector (distributed)

All imports are lazy to avoid dependency issues when optional
packages aren't installed.
"""

from typing import TYPE_CHECKING

# Lazy imports to avoid dependency issues
def get_vector_store(**kwargs):
    """Get ChromaDB vector store (lazy import)."""
    from src.infrastructure.vectordb.stores.chromadb_store import get_vector_store as _get
    return _get(**kwargs)

def get_faiss_store(**kwargs):
    """Get FAISS vector store (lazy import)."""
    from src.infrastructure.vectordb.stores.faiss_store import get_faiss_store as _get
    return _get(**kwargs)

def get_redis_store(**kwargs):
    """Get Redis vector store (lazy import)."""
    from src.infrastructure.vectordb.stores.redis_store import get_redis_store as _get
    return _get(**kwargs)

def reset_vector_store():
    """Reset ChromaDB vector store singleton."""
    from src.infrastructure.vectordb.stores.chromadb_store import reset_vector_store as _reset
    return _reset()

def reset_faiss_store():
    """Reset FAISS vector store singleton."""
    from src.infrastructure.vectordb.stores.faiss_store import reset_faiss_store as _reset
    return _reset()

def reset_redis_store():
    """Reset Redis vector store singleton."""
    from src.infrastructure.vectordb.stores.redis_store import reset_redis_store as _reset
    return _reset()


# Type hints only (no runtime import)
if TYPE_CHECKING:
    from src.infrastructure.vectordb.stores.chromadb_store import VectorStore
    from src.infrastructure.vectordb.stores.faiss_store import FAISSVectorStore
    from src.infrastructure.vectordb.stores.redis_store import RedisVectorStore
    
    # Alias
    ChromaDBStore = VectorStore


__all__ = [
    # ChromaDB
    'get_vector_store',
    'reset_vector_store',
    # FAISS
    'get_faiss_store',
    'reset_faiss_store',
    # Redis
    'get_redis_store',
    'reset_redis_store',
]
