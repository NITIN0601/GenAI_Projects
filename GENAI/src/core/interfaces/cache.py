"""
Cache interface definitions for three-tier caching.

Defines protocols for:
- ExtractionCache (Tier 1)
- EmbeddingCache (Tier 2)  
- QueryCache (Tier 3)
"""

from typing import Any, Dict, Generic, List, Optional, Protocol, TypeVar, runtime_checkable
from dataclasses import dataclass
from datetime import datetime


T = TypeVar('T')


@dataclass
class CacheStats:
    """Statistics for cache performance monitoring."""
    
    hits: int = 0
    misses: int = 0
    total_entries: int = 0
    size_bytes: int = 0
    last_cleanup: Optional[datetime] = None
    
    @property
    def hit_rate(self) -> float:
        """Calculate cache hit rate."""
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging/monitoring."""
        return {
            'hits': self.hits,
            'misses': self.misses,
            'hit_rate': f"{self.hit_rate:.2%}",
            'total_entries': self.total_entries,
            'size_mb': self.size_bytes / (1024 * 1024),
            'last_cleanup': self.last_cleanup.isoformat() if self.last_cleanup else None,
        }


@runtime_checkable
class CacheProvider(Protocol[T]):
    """
    Generic protocol for all cache tiers.
    
    Type parameter T is the cached value type:
    - ExtractionCache: T = ExtractionResult
    - EmbeddingCache: T = List[TableChunk]
    - QueryCache: T = RAGResponse
    """
    
    @property
    def name(self) -> str:
        """Cache name identifier."""
        ...
    
    @property
    def ttl_seconds(self) -> int:
        """Time-to-live in seconds."""
        ...
    
    @property
    def max_size(self) -> Optional[int]:
        """Maximum number of entries (None = unlimited)."""
        ...
    
    def get(self, key: str) -> Optional[T]:
        """
        Get cached value.
        
        Args:
            key: Cache key
            
        Returns:
            Cached value or None if not found/expired
        """
        ...
    
    def set(self, key: str, value: T, ttl: Optional[int] = None) -> None:
        """
        Set cached value.
        
        Args:
            key: Cache key
            value: Value to cache
            ttl: Override default TTL (seconds)
        """
        ...
    
    def delete(self, key: str) -> bool:
        """
        Delete cached value.
        
        Returns:
            True if deleted, False if not found
        """
        ...
    
    def exists(self, key: str) -> bool:
        """Check if key exists and is valid."""
        ...
    
    def clear(self) -> int:
        """
        Clear all cached values.
        
        Returns:
            Number of entries cleared
        """
        ...
    
    def get_stats(self) -> CacheStats:
        """Get cache statistics."""
        ...
    
    def cleanup_expired(self) -> int:
        """
        Remove expired entries.
        
        Returns:
            Number of entries removed
        """
        ...


@runtime_checkable
class RefreshableCache(CacheProvider[T], Protocol[T]):
    """
    Extended cache protocol with refresh capability.
    
    Used for QueryCache where users can request fresh results.
    """
    
    def invalidate_by_query(self, query_pattern: str) -> int:
        """
        Invalidate cached entries matching query pattern.
        
        Returns:
            Number of entries invalidated
        """
        ...
    
    def invalidate_by_source(self, source_id: str) -> int:
        """
        Invalidate cached entries related to a source document.
        
        Returns:
            Number of entries invalidated
        """
        ...
