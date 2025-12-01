"""
Vector store module.

Provides unified interface for multiple vector databases:
- ChromaDB
- FAISS
- Redis Vector

Example:
    >>> from src.vector_store.manager import VectorStoreManager
    >>> manager = VectorStoreManager(provider="chromadb")
    >>> manager.add_documents(documents)
"""

__version__ = "2.0.0"

__all__ = []

