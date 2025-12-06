"""
Infrastructure caching layer - Three-tier caching for RAG system.

Tiers:
- Tier 1: ExtractionCache (PDF extraction results)
- Tier 2: EmbeddingCache (embeddings by extraction hash + model)
- Tier 3: QueryCache (RAG responses with refresh option)
"""

from src.infrastructure.cache.base import BaseCache, CacheStats
from src.infrastructure.cache.extraction_cache import ExtractionCache
from src.infrastructure.cache.embedding_cache import EmbeddingCache
from src.infrastructure.cache.query_cache import QueryCache

__all__ = [
    'BaseCache',
    'CacheStats',
    'ExtractionCache',
    'EmbeddingCache',
    'QueryCache',
]
