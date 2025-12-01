"""
Embedding providers.

Supports multiple embedding providers with a unified interface.
"""

from src.embeddings.providers.base import (
    get_embedding_manager,
    EmbeddingManager,
    EmbeddingProvider,
    OpenAIEmbeddingProvider,
    LocalEmbeddingProvider
)

__all__ = [
    'get_embedding_manager',
    'EmbeddingManager',
    'EmbeddingProvider',
    'OpenAIEmbeddingProvider',
    'LocalEmbeddingProvider'
]
