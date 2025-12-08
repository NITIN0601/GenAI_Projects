"""
Redis caching backend.

Provides thread-safe singleton access to Redis cache with support for:
- Key-value caching with TTL
- LLM response caching
- Pickle serialization for complex objects

Example:
    >>> from src.infrastructure.cache import get_redis_cache
    >>> 
    >>> cache = get_redis_cache()
    >>> cache.set("key", {"data": "value"}, ttl=3600)
    >>> result = cache.get("key")
"""

from typing import Optional, Any, Dict
import pickle

from config.settings import settings
from src.core.singleton import ThreadSafeSingleton
from src.utils import get_logger

logger = get_logger(__name__)

try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False


class RedisCache(metaclass=ThreadSafeSingleton):
    """
    Redis cache implementation.
    
    Thread-safe singleton manager for Redis caching.
    
    Attributes:
        enabled: Whether caching is enabled
        client: Redis client instance
    """
    
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
                decode_responses=False
            )
            # Test connection
            self.client.ping()
            logger.info(f"Redis cache connected: {settings.REDIS_HOST}:{settings.REDIS_PORT}")
            
        except Exception as e:
            logger.error(f"Redis connection failed: {e}")
            logger.info("Continuing without cache...")
            self.enabled = False
            self.client = None
    
    @property
    def name(self) -> str:
        """Provider name (implements BaseProvider protocol)."""
        return "redis-cache"
    
    def is_available(self) -> bool:
        """Check if cache is available (implements BaseProvider protocol)."""
        if not self.enabled or not self.client:
            return False
        try:
            self.client.ping()
            return True
        except Exception:
            return False
    
    def health_check(self) -> Dict[str, Any]:
        """
        Perform health check (implements BaseProvider protocol).
        
        Returns:
            Dict with 'status' and optional details
        """
        try:
            available = self.is_available()
            return {
                "status": "ok" if available else "error",
                "enabled": self.enabled,
                "redis_host": settings.REDIS_HOST if self.enabled else None,
            }
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
            }
    
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

    def set_llm_response(self, query: str, response: str, context_hash: str) -> None:
        """Cache LLM response."""
        key = f"llm:{context_hash}:{hash(query)}"
        self.set(key, response, ttl=86400)  # 24 hours

    def clear(self) -> None:
        """Clear all cache."""
        if self.enabled and self.client:
            try:
                self.client.flushdb()
                logger.info("Cache cleared")
            except Exception as e:
                logger.error(f"Failed to clear cache: {e}")


def get_redis_cache() -> RedisCache:
    """
    Get or create global Redis cache instance.
    
    Thread-safe singleton accessor.
    
    Returns:
        RedisCache singleton instance
    """
    return RedisCache()


def reset_redis_cache() -> None:
    """
    Reset the Redis cache singleton.
    
    Useful for testing or reconfiguration.
    """
    RedisCache._reset_instance()
