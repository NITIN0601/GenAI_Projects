"""Redis caching layer for embeddings and LLM responses."""

import redis
import json
import hashlib
from typing import Optional, Any, List
import pickle

from config.settings import settings


class RedisCache:
    """
    Redis-based caching for:
    - Embeddings (avoid recomputation)
    - LLM responses (avoid redundant API calls)
    - PDF parsing results
    """
    
    def __init__(
        self,
        host: str = None,
        port: int = None,
        db: int = None,
        enabled: bool = None
    ):
        """
        Initialize Redis cache.
        
        Args:
            host: Redis host
            port: Redis port
            db: Redis database number
            enabled: Whether caching is enabled
        """
        self.enabled = enabled if enabled is not None else settings.REDIS_ENABLED
        
        if not self.enabled:
            print("Redis caching is disabled")
            self.client = None
            return
        
        try:
            self.client = redis.Redis(
                host=host or settings.REDIS_HOST,
                port=port or settings.REDIS_PORT,
                db=db or settings.REDIS_DB,
                decode_responses=False  # We'll handle encoding ourselves
            )
            # Test connection
            self.client.ping()
            print(f"Redis cache connected: {settings.REDIS_HOST}:{settings.REDIS_PORT}")
        except redis.ConnectionError as e:
            print(f"Redis connection failed: {e}")
            print("Continuing without cache...")
            self.enabled = False
            self.client = None
    
    def _generate_key(self, prefix: str, data: str) -> str:
        """Generate cache key using hash."""
        hash_obj = hashlib.md5(data.encode('utf-8'))
        return f"{prefix}:{hash_obj.hexdigest()}"
    
    def get_embedding(self, text: str) -> Optional[List[float]]:
        """
        Get cached embedding for text.
        
        Args:
            text: Input text
            
        Returns:
            Cached embedding or None
        """
        if not self.enabled or not self.client:
            return None
        
        try:
            key = self._generate_key("emb", text)
            cached = self.client.get(key)
            
            if cached:
                return pickle.loads(cached)
        except Exception as e:
            print(f"Cache get error: {e}")
        
        return None
    
    def set_embedding(self, text: str, embedding: List[float], ttl: int = None):
        """
        Cache embedding for text.
        
        Args:
            text: Input text
            embedding: Embedding vector
            ttl: Time to live in seconds (default: 24 hours)
        """
        if not self.enabled or not self.client:
            return
        
        try:
            key = self._generate_key("emb", text)
            ttl = ttl or settings.CACHE_TTL
            
            self.client.setex(
                key,
                ttl,
                pickle.dumps(embedding)
            )
        except Exception as e:
            print(f"Cache set error: {e}")
    
    def get_llm_response(self, query: str, context: str) -> Optional[str]:
        """
        Get cached LLM response.
        
        Args:
            query: User query
            context: Context provided to LLM
            
        Returns:
            Cached response or None
        """
        if not self.enabled or not self.client:
            return None
        
        try:
            cache_input = f"{query}|||{context}"
            key = self._generate_key("llm", cache_input)
            cached = self.client.get(key)
            
            if cached:
                return cached.decode('utf-8')
        except Exception as e:
            print(f"Cache get error: {e}")
        
        return None
    
    def set_llm_response(self, query: str, context: str, response: str, ttl: int = None):
        """
        Cache LLM response.
        
        Args:
            query: User query
            context: Context provided to LLM
            response: LLM response
            ttl: Time to live in seconds
        """
        if not self.enabled or not self.client:
            return
        
        try:
            cache_input = f"{query}|||{context}"
            key = self._generate_key("llm", cache_input)
            ttl = ttl or settings.CACHE_TTL
            
            self.client.setex(key, ttl, response.encode('utf-8'))
        except Exception as e:
            print(f"Cache set error: {e}")
    
    def get_pdf_parse(self, filename: str, file_hash: str) -> Optional[Any]:
        """
        Get cached PDF parse result.
        
        Args:
            filename: PDF filename
            file_hash: MD5 hash of file content
            
        Returns:
            Cached parse result or None
        """
        if not self.enabled or not self.client:
            return None
        
        try:
            key = f"pdf:{filename}:{file_hash}"
            cached = self.client.get(key)
            
            if cached:
                return pickle.loads(cached)
        except Exception as e:
            print(f"Cache get error: {e}")
        
        return None
    
    def set_pdf_parse(self, filename: str, file_hash: str, parse_result: Any, ttl: int = None):
        """
        Cache PDF parse result.
        
        Args:
            filename: PDF filename
            file_hash: MD5 hash of file content
            parse_result: Parse result to cache
            ttl: Time to live in seconds
        """
        if not self.enabled or not self.client:
            return
        
        try:
            key = f"pdf:{filename}:{file_hash}"
            ttl = ttl or settings.CACHE_TTL * 7  # Keep PDF cache longer (7 days)
            
            self.client.setex(
                key,
                ttl,
                pickle.dumps(parse_result)
            )
        except Exception as e:
            print(f"Cache set error: {e}")
    
    def clear_all(self):
        """Clear all cached data."""
        if not self.enabled or not self.client:
            return
        
        try:
            self.client.flushdb()
            print("Cache cleared")
        except Exception as e:
            print(f"Cache clear error: {e}")
    
    def get_stats(self) -> dict:
        """Get cache statistics."""
        if not self.enabled or not self.client:
            return {"enabled": False}
        
        try:
            info = self.client.info()
            
            # Count keys by prefix
            emb_keys = len(self.client.keys("emb:*"))
            llm_keys = len(self.client.keys("llm:*"))
            pdf_keys = len(self.client.keys("pdf:*"))
            
            return {
                "enabled": True,
                "total_keys": info.get('db0', {}).get('keys', 0),
                "embedding_keys": emb_keys,
                "llm_keys": llm_keys,
                "pdf_keys": pdf_keys,
                "memory_used": info.get('used_memory_human', 'N/A')
            }
        except Exception as e:
            return {"enabled": True, "error": str(e)}


# Global cache instance
_redis_cache: Optional[RedisCache] = None


def get_redis_cache() -> RedisCache:
    """Get or create global Redis cache instance."""
    global _redis_cache
    if _redis_cache is None:
        _redis_cache = RedisCache()
    return _redis_cache
