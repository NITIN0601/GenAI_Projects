"""
Caching mechanism for extraction results.
"""

import hashlib
import json
import pickle
from pathlib import Path
from typing import Optional
from datetime import datetime, timedelta
import logging

from src.infrastructure.extraction.base import ExtractionResult

logger = logging.getLogger(__name__)


class ExtractionCache:
    """File-based cache for extraction results."""
    
    def __init__(
        self,
        cache_dir: str = ".cache/extraction",
        ttl_hours: int = 24,
        enabled: bool = True
    ):
        """
        Initialize extraction cache.
        
        Args:
            cache_dir: Directory to store cache files
            ttl_hours: Time-to-live in hours
            enabled: Enable/disable caching
        """
        self.cache_dir = Path(cache_dir)
        self.ttl = timedelta(hours=ttl_hours)
        self.enabled = enabled
        
        if self.enabled:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"Extraction cache initialized at {self.cache_dir}")
    
    def get(self, pdf_path: str) -> Optional[ExtractionResult]:
        """
        Get cached extraction result.
        
        Args:
            pdf_path: Path to PDF file
            
        Returns:
            Cached ExtractionResult or None
        """
        if not self.enabled:
            return None
        
        cache_key = self._get_cache_key(pdf_path)
        cache_file = self.cache_dir / f"{cache_key}.pkl"
        
        if not cache_file.exists():
            logger.debug(f"Cache miss for {pdf_path}")
            return None
        
        # Check if cache is expired
        if self._is_expired(cache_file):
            logger.debug(f"Cache expired for {pdf_path}")
            cache_file.unlink()
            return None
        
        # Load from cache
        try:
            with open(cache_file, 'rb') as f:
                result = pickle.load(f)
            
            logger.info(f"Cache hit for {pdf_path} (backend: {result.backend.value})")
            return result
            
        except Exception as e:
            logger.error(f"Error loading cache for {pdf_path}: {e}")
            cache_file.unlink()
            return None
    
    def set(self, pdf_path: str, result: ExtractionResult) -> None:
        """
        Cache extraction result.
        
        Args:
            pdf_path: Path to PDF file
            result: Extraction result to cache
        """
        if not self.enabled:
            return
        
        cache_key = self._get_cache_key(pdf_path)
        cache_file = self.cache_dir / f"{cache_key}.pkl"
        
        try:
            with open(cache_file, 'wb') as f:
                pickle.dump(result, f)
            
            logger.info(f"Cached extraction for {pdf_path}")
            
        except Exception as e:
            logger.error(f"Error caching result for {pdf_path}: {e}")
    
    def invalidate(self, pdf_path: str) -> None:
        """
        Invalidate cache for a PDF.
        
        Args:
            pdf_path: Path to PDF file
        """
        if not self.enabled:
            return
        
        cache_key = self._get_cache_key(pdf_path)
        cache_file = self.cache_dir / f"{cache_key}.pkl"
        
        if cache_file.exists():
            cache_file.unlink()
            logger.info(f"Invalidated cache for {pdf_path}")
    
    def clear(self) -> int:
        """
        Clear all cache files.
        
        Returns:
            Number of files deleted
        """
        if not self.enabled:
            return 0
        
        count = 0
        for cache_file in self.cache_dir.glob("*.pkl"):
            cache_file.unlink()
            count += 1
        
        logger.info(f"Cleared {count} cache files")
        return count
    
    def cleanup_expired(self) -> int:
        """
        Remove expired cache files.
        
        Returns:
            Number of files deleted
        """
        if not self.enabled:
            return 0
        
        count = 0
        for cache_file in self.cache_dir.glob("*.pkl"):
            if self._is_expired(cache_file):
                cache_file.unlink()
                count += 1
        
        logger.info(f"Cleaned up {count} expired cache files")
        return count
    
    def get_stats(self) -> dict:
        """
        Get cache statistics.
        
        Returns:
            Dictionary with cache stats
        """
        if not self.enabled:
            return {"enabled": False}
        
        cache_files = list(self.cache_dir.glob("*.pkl"))
        total_size = sum(f.stat().st_size for f in cache_files)
        
        expired = sum(1 for f in cache_files if self._is_expired(f))
        
        return {
            "enabled": True,
            "total_files": len(cache_files),
            "expired_files": expired,
            "total_size_mb": total_size / (1024 * 1024),
            "cache_dir": str(self.cache_dir),
            "ttl_hours": self.ttl.total_seconds() / 3600
        }
    
    def _get_cache_key(self, pdf_path: str) -> str:
        """
        Generate cache key from PDF path.
        
        Uses MD5 hash of file path + file modification time.
        """
        pdf_file = Path(pdf_path)
        
        # Include file path and modification time in key
        key_data = f"{pdf_file.absolute()}_{pdf_file.stat().st_mtime}"
        
        return hashlib.md5(key_data.encode()).hexdigest()
    
    def _is_expired(self, cache_file: Path) -> bool:
        """Check if cache file is expired."""
        file_time = datetime.fromtimestamp(cache_file.stat().st_mtime)
        age = datetime.now() - file_time
        return age > self.ttl


class RedisCache(ExtractionCache):
    """Redis-based cache for extraction results (future implementation)."""
    
    def __init__(self, redis_url: str = "redis://localhost:6379", **kwargs):
        """
        Initialize Redis cache.
        
        Args:
            redis_url: Redis connection URL
            **kwargs: Additional cache options
        """
        super().__init__(**kwargs)
        self.redis_url = redis_url
        # TODO: Implement Redis connection
        logger.warning("RedisCache not yet implemented, falling back to file cache")
