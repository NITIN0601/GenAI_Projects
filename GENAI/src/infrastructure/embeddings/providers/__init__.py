"""
Embedding providers.

Supports multiple embedding providers with a unified interface.
"""

from src.infrastructure.embeddings.providers.base import EmbeddingProvider
from src.infrastructure.embeddings.providers.custom_api_provider import CustomAPIEmbeddingProvider

__all__ = [
    'EmbeddingProvider',
    'CustomAPIEmbeddingProvider',
]
