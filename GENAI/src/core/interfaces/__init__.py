"""
Interface definitions for GENAI providers and services.

Uses Python's Protocol (structural subtyping) for type-safe interfaces
without requiring inheritance.
"""

from src.core.interfaces.provider import (
    BaseProvider,
    LLMProvider,
    EmbeddingProvider,
    VectorStoreProvider,
    ExtractionProvider,
)
from src.core.interfaces.cache import (
    CacheProvider,
    CacheStats,
)

__all__ = [
    # Providers
    'BaseProvider',
    'LLMProvider',
    'EmbeddingProvider',
    'VectorStoreProvider',
    'ExtractionProvider',
    # Cache
    'CacheProvider',
    'CacheStats',
]
