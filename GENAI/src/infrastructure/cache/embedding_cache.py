"""
Tier 2: Embedding Cache

Model-aware caching for embeddings.
Key: extraction_hash + embedding_model (invalidates on model change)
TTL: 90 days (embeddings are stable for same model)
"""

from pathlib import Path
from typing import Optional, List, Any
import logging
from src.utils import get_logger

from src.infrastructure.cache.base import BaseCache

logger = get_logger(__name__)


class EmbeddingCache(BaseCache[List[Any]]):
    """
    Model-aware embedding cache.
    
    Cache key includes the embedding model name, so changing
    models automatically invalidates cached embeddings.
    
    Example:
        >>> cache = EmbeddingCache()
        >>> chunks = cache.get_embeddings(extraction_hash, model="all-MiniLM-L6-v2")
        >>> if chunks is None:
        ...     chunks = embedder.embed(tables)
        ...     cache.set_embeddings(extraction_hash, chunks, model="all-MiniLM-L6-v2")
    """
    
    DEFAULT_TTL_HOURS = 24 * 90  # 90 days
    
    def __init__(
        self,
        cache_dir: Optional[Path] = None,
        ttl_hours: int = DEFAULT_TTL_HOURS,
        max_entries: Optional[int] = 1000,
        enabled: bool = True,
    ):
        """
        Initialize embedding cache.
        
        Args:
            cache_dir: Cache directory (default: .cache/embeddings)
            ttl_hours: TTL in hours (default: 90 days)
            max_entries: Max entries (default: 1000)
            enabled: Enable caching
        """
        if cache_dir is None:
            from src.core.paths import get_paths
            cache_dir = get_paths().embedding_cache_dir
        
        super().__init__(
            cache_dir=cache_dir,
            name="EmbeddingCache",
            ttl_hours=ttl_hours,
            max_entries=max_entries,
            enabled=enabled,
        )
    
    def _get_model_key(self, extraction_hash: str, model: Optional[str] = None) -> str:
        """
        Generate cache key including model name.
        
        Args:
            extraction_hash: Hash from extraction cache
            model: Embedding model name (default: from settings)
            
        Returns:
            Cache key: {extraction_hash}_{model}
        """
        if model is None:
            from config.settings import settings
            model = settings.EMBEDDING_MODEL
        
        # Normalize model name (remove special chars)
        model_clean = model.replace('/', '_').replace(':', '_')
        
        return f"{extraction_hash}_{model_clean}"
    
    def get_embeddings(
        self,
        extraction_hash: str,
        model: Optional[str] = None,
    ) -> Optional[List[Any]]:
        """
        Get cached embeddings for extraction hash + model.
        
        Args:
            extraction_hash: Hash from extraction cache
            model: Embedding model (default: from settings)
            
        Returns:
            List of TableChunk with embeddings, or None
        """
        key = self._get_model_key(extraction_hash, model)
        return self.get(key)
    
    def set_embeddings(
        self,
        extraction_hash: str,
        chunks: List[Any],
        model: Optional[str] = None,
    ) -> str:
        """
        Cache embeddings for extraction hash + model.
        
        Args:
            extraction_hash: Hash from extraction cache
            chunks: List of TableChunk with embeddings
            model: Embedding model (default: from settings)
            
        Returns:
            Cache key used
        """
        key = self._get_model_key(extraction_hash, model)
        self.set(key, chunks)
        
        logger.info(
            f"Cached embeddings: {len(chunks)} chunks for "
            f"extraction={extraction_hash[:12]}... model={model or 'default'}"
        )
        
        return key
    
    def exists_embeddings(
        self,
        extraction_hash: str,
        model: Optional[str] = None,
    ) -> bool:
        """Check if embeddings exist for extraction hash + model."""
        key = self._get_model_key(extraction_hash, model)
        return self.exists(key)
    
    def invalidate_for_extraction(self, extraction_hash: str) -> int:
        """
        Invalidate all embeddings for an extraction (all models).
        
        Args:
            extraction_hash: Hash from extraction cache
            
        Returns:
            Number of entries invalidated
        """
        count = 0
        for cache_file in self.cache_dir.glob(f"{extraction_hash}_*.pkl"):
            cache_file.unlink()
            count += 1
        
        logger.info(f"Invalidated {count} embedding caches for {extraction_hash[:12]}...")
        return count
