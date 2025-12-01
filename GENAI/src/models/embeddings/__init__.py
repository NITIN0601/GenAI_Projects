"""
Models - Embeddings module.

Provides unified interface for embedding providers:
- Local (sentence-transformers) - FREE
- OpenAI (text-embedding-3-small) - PAID
- Custom API (bearer token auth) - YOUR API

Usage:
    from models.embeddings import get_embedding_manager
    
    # Auto-loads from settings.EMBEDDING_PROVIDER
    em = get_embedding_manager()
"""

from src.models.embeddings.providers import (
    EmbeddingProvider,
    OpenAIEmbeddingProvider,
    LocalEmbeddingProvider,
    EmbeddingManager,
    get_embedding_manager
)

__all__ = [
    'EmbeddingProvider',
    'OpenAIEmbeddingProvider',
    'LocalEmbeddingProvider',
    'EmbeddingManager',
    'get_embedding_manager',
]
