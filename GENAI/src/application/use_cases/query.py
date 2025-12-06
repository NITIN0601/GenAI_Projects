"""
Query Use Case - RAG queries with caching.

Orchestrates:
1. Query cache lookup (Tier 3)
2. Vector retrieval
3. LLM generation
4. Response caching
5. Optional evaluation
"""

from typing import Optional, Dict, Any, List
from functools import lru_cache
import logging

from src.domain.queries import RAGQuery, RAGResponse
from src.infrastructure.cache import QueryCache

logger = logging.getLogger(__name__)


class QueryUseCase:
    """
    RAG query execution with caching.
    
    Wraps the existing query pipeline with:
    - Query cache (Tier 3) for instant repeated responses
    - Force refresh option for users
    - Cache statistics tracking
    
    Example:
        >>> use_case = QueryUseCase()
        >>> response = use_case.query("What was revenue in Q1?")
        >>> print(f"From cache: {response.from_cache}")
        >>> 
        >>> # Force fresh results
        >>> response = use_case.query("What was revenue in Q1?", force_refresh=True)
    """
    
    def __init__(
        self,
        query_cache: Optional[QueryCache] = None,
        cache_enabled: bool = True,
    ):
        """
        Initialize query use case.
        
        Args:
            query_cache: Tier 3 cache instance
            cache_enabled: Enable query caching
        """
        self.query_cache = query_cache or QueryCache(enabled=cache_enabled)
        self.cache_enabled = cache_enabled
        
        # Lazy load the actual query engine
        self._query_engine = None
        
        logger.info(f"QueryUseCase initialized (cache: {'enabled' if cache_enabled else 'disabled'})")
    
    @property
    def query_engine(self):
        """Lazy load query engine."""
        if self._query_engine is None:
            from src.rag.pipeline import QueryEngine
            self._query_engine = QueryEngine()
        return self._query_engine
    
    def query(
        self,
        query: str,
        filters: Optional[Dict[str, Any]] = None,
        top_k: int = 5,
        force_refresh: bool = False,
        include_evaluation: bool = False,
    ) -> RAGResponse:
        """
        Execute RAG query with caching.
        
        Args:
            query: User question
            filters: Metadata filters (year, quarter, table_type, etc.)
            top_k: Number of results to retrieve
            force_refresh: Force fresh search (skip cache)
            include_evaluation: Run evaluation on response
            
        Returns:
            RAGResponse with answer, sources, and cache indicator
        """
        # Check cache first (unless force_refresh)
        if self.cache_enabled and not force_refresh:
            cached_response = self.query_cache.get_response(query, filters, top_k)
            if cached_response:
                logger.info(f"Query cache hit: '{query[:40]}...'")
                return cached_response
        
        # Execute query through pipeline
        logger.info(f"Executing query: '{query[:40]}...'")
        
        try:
            response = self.query_engine.query(
                query=query,
                filters=filters,
                top_k=top_k,
                use_cache=False,  # We handle caching at this layer
            )
            
            # Cache the response
            if self.cache_enabled:
                self.query_cache.set_response(query, response, filters, top_k)
            
            return response
            
        except Exception as e:
            logger.error(f"Query failed: {e}")
            return RAGResponse(
                answer=f"I encountered an error processing your query: {str(e)}",
                sources=[],
                confidence=0.0,
                retrieved_chunks=0,
                from_cache=False,
            )
    
    def query_from_request(self, request: RAGQuery) -> RAGResponse:
        """
        Execute query from RAGQuery request object.
        
        Args:
            request: RAGQuery with query, filters, top_k, etc.
            
        Returns:
            RAGResponse
        """
        return self.query(
            query=request.query,
            filters=request.filters,
            top_k=request.top_k,
            force_refresh=request.force_refresh,
        )
    
    def invalidate_cache(self, query: Optional[str] = None) -> int:
        """
        Invalidate query cache.
        
        Args:
            query: Specific query to invalidate (None = clear all)
            
        Returns:
            Number of entries invalidated
        """
        if query:
            success = self.query_cache.invalidate_query(query)
            return 1 if success else 0
        else:
            return self.query_cache.clear()
    
    def get_cache_stats(self) -> dict:
        """Get query cache statistics."""
        return self.query_cache.get_stats().to_dict()


# Singleton instance
_query_use_case: Optional[QueryUseCase] = None


def get_query_use_case() -> QueryUseCase:
    """Get global QueryUseCase instance."""
    global _query_use_case
    if _query_use_case is None:
        _query_use_case = QueryUseCase()
    return _query_use_case
