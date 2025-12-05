"""
Caching module.

Provides caching backends for improved performance.
"""

from src.cache.backends.redis_cache import RedisCache, get_redis_cache

__version__ = "2.0.0"

__all__ = [
    'RedisCache',
    'get_redis_cache',
]
