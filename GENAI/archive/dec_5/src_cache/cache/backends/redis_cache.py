"""
Redis caching backend.

Implements caching interface using Redis.
"""

from typing import Optional, Any, Dict
import json
import logging
import pickle

from config.settings import settings
from src.utils import get_logger

logger = get_logger(__name__)

try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False


class RedisCache:
    """Redis cache implementation."""
    
    def __init__(self):
        """Initialize Redis cache."""
        self.enabled = settings.REDIS_ENABLED
        self.client = None
        
        if not self.enabled:
            logger.info("Redis caching is disabled")
            return
            
        if not REDIS_AVAILABLE:
            logger.warning("Redis module not installed. Install with: pip install redis")
            logger.info("Continuing without cache...")
            self.enabled = False
            return
            
        try:
            self.client = redis.Redis(
                host=settings.REDIS_HOST,
                port=settings.REDIS_PORT,
                db=settings.REDIS_DB,
                password=settings.REDIS_PASSWORD,
                decode_responses=False  # We handle decoding manually for complex objects
            )
            # Test connection
            self.client.ping()
            logger.info(f"Redis cache connected: {settings.REDIS_HOST}:{settings.REDIS_PORT}")
            
        except Exception as e:
            logger.error(f"Redis connection failed: {e}")
            logger.info("Continuing without cache...")
            self.enabled = False
            self.client = None
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        if not self.enabled or not self.client:
            return None
            
        try:
            data = self.client.get(key)
            if data:
                return pickle.loads(data)
            return None
        except Exception as e:
            logger.error(f"Cache get error: {e}")
            return None
            
    def set(self, key: str, value: Any, ttl: int = 3600) -> bool:
        """Set value in cache."""
        if not self.enabled or not self.client:
            return False
            
        try:
            data = pickle.dumps(value)
            return self.client.setex(key, ttl, data)
        except Exception as e:
            logger.error(f"Cache set error: {e}")
            return False

    def get_llm_response(self, query: str, context_hash: str) -> Optional[str]:
        """Get cached LLM response."""
        key = f"llm:{context_hash}:{hash(query)}"
        return self.get(key)

    def set_llm_response(self, query: str, response: str, context_hash: str):
        """Cache LLM response."""
        key = f"llm:{context_hash}:{hash(query)}"
        self.set(key, response, ttl=86400) # 24 hours

    def clear(self):
        """Clear all cache."""
        if self.enabled and self.client:
            try:
                self.client.flushdb()
                logger.info("Cache cleared")
            except Exception as e:
                logger.error(f"Failed to clear cache: {e}")


# Global instance
_redis_cache: Optional[RedisCache] = None

def get_redis_cache() -> RedisCache:
    """Get global Redis cache instance."""
    global _redis_cache
    if _redis_cache is None:
        _redis_cache = RedisCache()
    return _redis_cache
