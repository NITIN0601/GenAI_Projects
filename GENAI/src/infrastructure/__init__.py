"""
Infrastructure layer - External integrations and adapters.

Contains implementations that interface with external systems:
- cache: Three-tier caching (extraction, embedding, query)
- vectordb: Vector database providers (future)
- llm: LLM providers (future)
- embeddings: Embedding providers (future)
"""

from src.infrastructure.cache import (
    BaseCache,
    CacheStats,
    ExtractionCache,
    EmbeddingCache,
    QueryCache,
)

__all__ = [
    # Cache
    'BaseCache',
    'CacheStats',
    'ExtractionCache',
    'EmbeddingCache',
    'QueryCache',
]
