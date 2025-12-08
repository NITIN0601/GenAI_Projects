"""
Vector Store Module.

Provides unified interface for multiple vector database backends:
- ChromaDB (persistent, default)
- FAISS (high-performance, in-memory)
- Redis Vector (distributed, production-scale)

Thread-Safe Singleton:
    The VectorDBManager uses ThreadSafeSingleton pattern for consistent
    instance management across the application.

Example:
    >>> from src.infrastructure.vectordb import get_vectordb_manager
    >>> 
    >>> # Get singleton instance
    >>> vectordb = get_vectordb_manager()
    >>> 
    >>> # Add chunks
    >>> vectordb.add_chunks(chunks)
    >>> 
    >>> # Search
    >>> results = vectordb.search("revenue growth", top_k=5)
    
Configuration:
    Set VECTORDB_PROVIDER in .env or settings:
    - chromadb: Persistent, easy to use
    - faiss: High-performance, optimized for speed
    - redis: Distributed, production-scale
"""

from src.infrastructure.vectordb.manager import (
    VectorDBManager,
    VectorDBInterface,
    get_vectordb_manager,
    reset_vectordb_manager,
)

__version__ = "2.1.0"

__all__ = [
    # Interface
    'VectorDBInterface',
    # Manager
    'VectorDBManager',
    'get_vectordb_manager',
    'reset_vectordb_manager',
]
