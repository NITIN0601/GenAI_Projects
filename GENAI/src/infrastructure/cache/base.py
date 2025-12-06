"""
Base cache implementation with common functionality.

Provides:
- File-based caching with pickle serialization
- TTL (time-to-live) expiration
- Size limits with LRU eviction
- Hit/miss metrics tracking
"""

import hashlib
import pickle
import json
from pathlib import Path
from typing import Any, Dict, Generic, Optional, TypeVar, List
from datetime import datetime, timedelta
from dataclasses import dataclass, field
import logging
import os

logger = logging.getLogger(__name__)

T = TypeVar('T')


@dataclass
class CacheStats:
    """Cache performance statistics."""
    
    hits: int = 0
    misses: int = 0
    total_entries: int = 0
    size_bytes: int = 0
    evictions: int = 0
    last_cleanup: Optional[datetime] = None
    
    @property
    def hit_rate(self) -> float:
        """Calculate cache hit rate."""
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'hits': self.hits,
            'misses': self.misses,
            'hit_rate': f"{self.hit_rate:.1%}",
            'total_entries': self.total_entries,
            'size_mb': round(self.size_bytes / (1024 * 1024), 2),
            'evictions': self.evictions,
            'last_cleanup': self.last_cleanup.isoformat() if self.last_cleanup else None,
        }


class BaseCache(Generic[T]):
    """
    Base file-based cache with TTL and size limits.
    
    Features:
    - Pickle serialization for complex objects
    - Configurable TTL expiration
    - Optional max size with LRU eviction
    - Hit/miss tracking
    """
    
    def __init__(
        self,
        cache_dir: Path,
        name: str = "cache",
        ttl_hours: int = 24,
        max_entries: Optional[int] = None,
        enabled: bool = True,
    ):
        """
        Initialize base cache.
        
        Args:
            cache_dir: Directory for cache files
            name: Cache name for logging
            ttl_hours: Time-to-live in hours
            max_entries: Max entries before eviction (None = unlimited)
            enabled: Enable/disable caching
        """
        self.cache_dir = Path(cache_dir)
        self.name = name
        self.ttl = timedelta(hours=ttl_hours)
        self.max_entries = max_entries
        self.enabled = enabled
        self.stats = CacheStats()
        
        # Metadata file for tracking
        self._metadata_file = self.cache_dir / "_metadata.json"
        self._metadata: Dict[str, Any] = {}
        
        if self.enabled:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            self._load_metadata()
            logger.info(f"{self.name} cache initialized at {self.cache_dir}")
    
    # =========================================================================
    # Core Operations
    # =========================================================================
    
    def get(self, key: str) -> Optional[T]:
        """Get cached value by key."""
        if not self.enabled:
            return None
        
        cache_file = self._get_cache_file(key)
        
        if not cache_file.exists():
            self.stats.misses += 1
            logger.debug(f"[{self.name}] Cache miss: {key[:16]}...")
            return None
        
        # Check expiration
        if self._is_expired(cache_file):
            self.stats.misses += 1
            cache_file.unlink()
            self._remove_from_metadata(key)
            logger.debug(f"[{self.name}] Cache expired: {key[:16]}...")
            return None
        
        # Load from cache
        try:
            with open(cache_file, 'rb') as f:
                value = pickle.load(f)
            
            self.stats.hits += 1
            self._update_access_time(key)
            logger.debug(f"[{self.name}] Cache hit: {key[:16]}...")
            return value
            
        except Exception as e:
            self.stats.misses += 1
            logger.error(f"[{self.name}] Error loading cache: {e}")
            cache_file.unlink()
            self._remove_from_metadata(key)
            return None
    
    def set(self, key: str, value: T, ttl_hours: Optional[int] = None) -> None:
        """Set cached value."""
        if not self.enabled:
            return
        
        # Evict if at max capacity
        if self.max_entries and len(self._metadata) >= self.max_entries:
            self._evict_lru()
        
        cache_file = self._get_cache_file(key)
        
        try:
            with open(cache_file, 'wb') as f:
                pickle.dump(value, f)
            
            # Update metadata
            self._metadata[key] = {
                'created': datetime.now().isoformat(),
                'accessed': datetime.now().isoformat(),
                'ttl_hours': ttl_hours or self.ttl.total_seconds() / 3600,
                'size': cache_file.stat().st_size,
            }
            self._save_metadata()
            
            logger.debug(f"[{self.name}] Cached: {key[:16]}...")
            
        except Exception as e:
            logger.error(f"[{self.name}] Error caching: {e}")
    
    def delete(self, key: str) -> bool:
        """Delete cached value."""
        if not self.enabled:
            return False
        
        cache_file = self._get_cache_file(key)
        
        if cache_file.exists():
            cache_file.unlink()
            self._remove_from_metadata(key)
            return True
        
        return False
    
    def exists(self, key: str) -> bool:
        """Check if key exists and is valid."""
        if not self.enabled:
            return False
        
        cache_file = self._get_cache_file(key)
        return cache_file.exists() and not self._is_expired(cache_file)
    
    def clear(self) -> int:
        """Clear all cache entries."""
        if not self.enabled:
            return 0
        
        count = 0
        for cache_file in self.cache_dir.glob("*.pkl"):
            cache_file.unlink()
            count += 1
        
        self._metadata.clear()
        self._save_metadata()
        
        logger.info(f"[{self.name}] Cleared {count} entries")
        return count
    
    # =========================================================================
    # Maintenance
    # =========================================================================
    
    def cleanup_expired(self) -> int:
        """Remove expired entries."""
        if not self.enabled:
            return 0
        
        count = 0
        for cache_file in self.cache_dir.glob("*.pkl"):
            if self._is_expired(cache_file):
                cache_file.unlink()
                count += 1
        
        # Sync metadata
        valid_keys = {f.stem for f in self.cache_dir.glob("*.pkl")}
        self._metadata = {k: v for k, v in self._metadata.items() if k in valid_keys}
        self._save_metadata()
        
        self.stats.last_cleanup = datetime.now()
        logger.info(f"[{self.name}] Cleaned up {count} expired entries")
        return count
    
    def get_stats(self) -> CacheStats:
        """Get cache statistics."""
        if self.enabled:
            files = list(self.cache_dir.glob("*.pkl"))
            self.stats.total_entries = len(files)
            self.stats.size_bytes = sum(f.stat().st_size for f in files)
        return self.stats
    
    # =========================================================================
    # Internal Methods
    # =========================================================================
    
    def _get_cache_file(self, key: str) -> Path:
        """Get cache file path for key."""
        return self.cache_dir / f"{key}.pkl"
    
    def _is_expired(self, cache_file: Path) -> bool:
        """Check if cache file is expired."""
        file_time = datetime.fromtimestamp(cache_file.stat().st_mtime)
        
        # Check custom TTL from metadata
        key = cache_file.stem
        if key in self._metadata:
            ttl_hours = self._metadata[key].get('ttl_hours', self.ttl.total_seconds() / 3600)
            ttl = timedelta(hours=ttl_hours)
        else:
            ttl = self.ttl
        
        return datetime.now() - file_time > ttl
    
    def _evict_lru(self) -> None:
        """Evict least recently used entry."""
        if not self._metadata:
            return
        
        # Find LRU entry
        lru_key = min(
            self._metadata.keys(),
            key=lambda k: self._metadata[k].get('accessed', '1970-01-01')
        )
        
        # Remove it
        self.delete(lru_key)
        self.stats.evictions += 1
        logger.debug(f"[{self.name}] Evicted LRU: {lru_key[:16]}...")
    
    def _update_access_time(self, key: str) -> None:
        """Update last access time in metadata."""
        if key in self._metadata:
            self._metadata[key]['accessed'] = datetime.now().isoformat()
            self._save_metadata()
    
    def _remove_from_metadata(self, key: str) -> None:
        """Remove key from metadata."""
        if key in self._metadata:
            del self._metadata[key]
            self._save_metadata()
    
    def _load_metadata(self) -> None:
        """Load metadata from file."""
        if self._metadata_file.exists():
            try:
                with open(self._metadata_file, 'r') as f:
                    self._metadata = json.load(f)
            except Exception:
                self._metadata = {}
    
    def _save_metadata(self) -> None:
        """Save metadata to file."""
        try:
            with open(self._metadata_file, 'w') as f:
                json.dump(self._metadata, f, indent=2)
        except Exception as e:
            logger.error(f"[{self.name}] Error saving metadata: {e}")
