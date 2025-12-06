"""
Tier 3: Query Cache

User query result caching with refresh option.
Key: query_text + filters + top_k (hashed)
TTL: 24 hours (RAG results may change with new data)
"""

import hashlib
import json
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime
import logging

from src.infrastructure.cache.base import BaseCache

logger = logging.getLogger(__name__)


class QueryCache(BaseCache[Any]):
    """
    Query result cache with refresh support.
    
    Caches RAG responses for identical queries. Users can
    force a refresh to get fresh results.
    
    Example:
        >>> cache = QueryCache()
        >>> response = cache.get_response("What was revenue?", filters={"year": 2025})
        >>> if response is None or force_refresh:
        ...     response = rag.query("What was revenue?", filters={"year": 2025})
        ...     cache.set_response("What was revenue?", response, filters={"year": 2025})
    """
    
    DEFAULT_TTL_HOURS = 24  # 24 hours
    
    def __init__(
        self,
        cache_dir: Optional[Path] = None,
        ttl_hours: int = DEFAULT_TTL_HOURS,
        max_entries: Optional[int] = 200,
        enabled: bool = True,
    ):
        """
        Initialize query cache.
        
        Args:
            cache_dir: Cache directory (default: .cache/queries)
            ttl_hours: TTL in hours (default: 24)
            max_entries: Max entries (default: 200)
            enabled: Enable caching
        """
        if cache_dir is None:
            from src.core.paths import get_paths
            cache_dir = get_paths().query_cache_dir
        
        super().__init__(
            cache_dir=cache_dir,
            name="QueryCache",
            ttl_hours=ttl_hours,
            max_entries=max_entries,
            enabled=enabled,
        )
        
        # Query -> key mapping for invalidation
        self._query_keys: Dict[str, str] = {}
    
    def _generate_key(
        self,
        query: str,
        filters: Optional[Dict[str, Any]] = None,
        top_k: int = 5,
    ) -> str:
        """
        Generate cache key from query parameters.
        
        Args:
            query: User query text
            filters: Metadata filters
            top_k: Number of results
            
        Returns:
            MD5 hash of normalized query parameters
        """
        # Normalize for consistent hashing
        query_normalized = query.strip().lower()
        filters_str = json.dumps(filters or {}, sort_keys=True)
        
        key_data = f"{query_normalized}|{filters_str}|{top_k}"
        
        return hashlib.md5(key_data.encode()).hexdigest()
    
    def get_response(
        self,
        query: str,
        filters: Optional[Dict[str, Any]] = None,
        top_k: int = 5,
    ) -> Optional[Any]:
        """
        Get cached RAG response.
        
        Args:
            query: User query
            filters: Metadata filters
            top_k: Number of results
            
        Returns:
            Cached RAGResponse with from_cache=True, or None
        """
        key = self._generate_key(query, filters, top_k)
        response = self.get(key)
        
        if response is not None:
            # Mark as from cache
            if hasattr(response, 'from_cache'):
                response.from_cache = True
            logger.info(f"Query cache hit: '{query[:50]}...'")
        
        return response
    
    def set_response(
        self,
        query: str,
        response: Any,
        filters: Optional[Dict[str, Any]] = None,
        top_k: int = 5,
    ) -> str:
        """
        Cache RAG response.
        
        Args:
            query: User query
            response: RAGResponse to cache
            filters: Metadata filters
            top_k: Number of results
            
        Returns:
            Cache key used
        """
        key = self._generate_key(query, filters, top_k)
        self.set(key, response)
        
        # Track query -> key mapping
        self._query_keys[query.strip().lower()] = key
        
        logger.info(f"Cached query response: '{query[:50]}...'")
        
        return key
    
    def invalidate_query(self, query: str) -> bool:
        """
        Invalidate cache for a specific query (all filter variants).
        
        Note: Only invalidates exact query matches tracked.
        For full invalidation, use clear().
        
        Args:
            query: Query text
            
        Returns:
            True if invalidated, False if not found
        """
        query_lower = query.strip().lower()
        
        if query_lower in self._query_keys:
            key = self._query_keys[query_lower]
            success = self.delete(key)
            del self._query_keys[query_lower]
            return success
        
        return False
    
    def invalidate_by_source(self, source_doc: str) -> int:
        """
        Invalidate all queries that may have used a source document.
        
        Use this when a document is updated/reprocessed.
        Currently clears all cache (conservative approach).
        
        Args:
            source_doc: Source document filename
            
        Returns:
            Number of entries cleared
        """
        # Conservative: clear all query cache when data changes
        # Future: track source -> query relationships
        logger.info(f"Invalidating query cache due to source update: {source_doc}")
        return self.clear()
    
    def invalidate_by_age(self, max_age_hours: int) -> int:
        """
        Invalidate entries older than specified age.
        
        Args:
            max_age_hours: Maximum age in hours
            
        Returns:
            Number of entries invalidated
        """
        count = 0
        cutoff = datetime.now()
        
        for key, meta in list(self._metadata.items()):
            created = datetime.fromisoformat(meta.get('created', '1970-01-01'))
            age_hours = (cutoff - created).total_seconds() / 3600
            
            if age_hours > max_age_hours:
                self.delete(key)
                count += 1
        
        logger.info(f"Invalidated {count} queries older than {max_age_hours} hours")
        return count
