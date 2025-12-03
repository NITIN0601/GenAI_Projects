"""
Embedding providers.

Supports multiple embedding providers with a unified interface.
"""

from src.embeddings.providers.base import EmbeddingProvider

# Note: Manager functions are in src.embeddings.manager
# Custom provider implementation is in src.embeddings.providers.custom_api_provider

__all__ = ['EmbeddingProvider']
