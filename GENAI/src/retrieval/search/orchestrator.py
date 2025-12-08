"""
Search Orchestrator - Coordinates multiple search strategies.

Industry standard: Orchestrator Pattern
- Manages strategy lifecycle
- Handles caching
- Coordinates reranking
- Monitors performance
- Provides unified interface

Thread-Safe Singleton:
    Uses ThreadSafeSingleton pattern for consistent instance management.

This is the MAIN ENTRY POINT for search operations.

Example:
    >>> from src.retrieval.search import get_search_orchestrator
    >>> 
    >>> orchestrator = get_search_orchestrator()
    >>> results = orchestrator.search("revenue in Q1", top_k=5)
"""

from typing import List, Dict, Any, Optional, TYPE_CHECKING
from datetime import datetime

from src.core.singleton import ThreadSafeSingleton
from src.retrieval.search.base import (
    SearchStrategy,
    SearchConfig,
    SearchResult
)
from src.retrieval.search.factory import SearchStrategyFactory
from src.utils import get_logger

logger = get_logger(__name__)

if TYPE_CHECKING:
    from src.infrastructure.vectordb.manager import VectorDBManager
    from src.infrastructure.embeddings.manager import EmbeddingManager
    from src.infrastructure.llm.manager import LLMManager


class SearchOrchestrator(metaclass=ThreadSafeSingleton):
    """
    Orchestrates search strategies with caching, reranking, and monitoring.
    
    Thread-safe singleton manager for search operations.
    
    This is the main interface for all search operations.
    
    Features:
    - Strategy selection and execution
    - Result caching (optional)
    - Re-ranking (optional)
    - Performance monitoring
    - Multi-strategy ensemble (RRF fusion)
    - Fallback strategies
    
    Attributes:
        vector_store: Vector database instance
        embedding_manager: Embedding manager
        llm_manager: LLM manager (for HyDE/Multi-Query)
        default_strategy: Default search strategy
    
    Usage:
        >>> orchestrator = get_search_orchestrator()
        >>> results = orchestrator.search(
        ...     query="What was revenue in Q1?",
        ...     strategy=SearchStrategy.HYBRID,
        ...     top_k=10
        ... )
    """
    
    def __init__(
        self,
        vector_store: Optional["VectorDBManager"] = None,
        embedding_manager: Optional["EmbeddingManager"] = None,
        llm_manager: Optional["LLMManager"] = None,
        default_strategy: SearchStrategy = SearchStrategy.HYBRID,
        enable_caching: bool = False,
        enable_reranking: bool = False
    ):
        """
        Initialize search orchestrator.
        
        Args:
            vector_store: Vector store instance (auto-created if None)
            embedding_manager: Embedding manager (auto-created if None)
            llm_manager: LLM manager (optional, for HyDE/Multi-Query)
            default_strategy: Default search strategy
            enable_caching: Enable result caching
            enable_reranking: Enable cross-encoder re-ranking
        """
        # Lazy initialization of dependencies
        self._vector_store = vector_store
        self._embedding_manager = embedding_manager
        self._llm_manager = llm_manager
        self.default_strategy = default_strategy
        
        # Components
        self.factory = SearchStrategyFactory()
        self.cache = None
        self.reranker = None
        
        # Initialize cache if enabled
        if enable_caching:
            self._init_cache()
        
        # Initialize reranker if enabled
        if enable_reranking:
            self._init_reranker()
        
        # Performance tracking
        self.metrics: Dict[str, Any] = {
            "total_searches": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "strategy_usage": {},
            "average_latency_ms": 0.0,
            "total_latency_ms": 0.0
        }
        
        logger.info(
            f"Search orchestrator initialized: "
            f"default_strategy={default_strategy}, "
            f"caching={enable_caching}, "
            f"reranking={enable_reranking}"
        )
    
    def _init_cache(self) -> None:
        """Initialize search result cache."""
        try:
            from src.infrastructure.cache import get_redis_cache
            self.cache = get_redis_cache()
            logger.info("Search caching enabled")
        except Exception as e:
            logger.warning(f"Failed to initialize cache: {e}")
    
    def _init_reranker(self) -> None:
        """Initialize cross-encoder reranker."""
        try:
            from src.retrieval.reranking.cross_encoder import CrossEncoderReranker
            self.reranker = CrossEncoderReranker()
            logger.info("Search re-ranking enabled")
        except Exception as e:
            logger.warning(f"Failed to initialize reranker: {e}")
    
    @property
    def vector_store(self) -> "VectorDBManager":
        """Get vector store (lazy initialization)."""
        if self._vector_store is None:
            from src.infrastructure.vectordb import get_vectordb_manager
            self._vector_store = get_vectordb_manager()
        return self._vector_store
    
    @property
    def embedding_manager(self) -> "EmbeddingManager":
        """Get embedding manager (lazy initialization)."""
        if self._embedding_manager is None:
            from src.infrastructure.embeddings import get_embedding_manager
            self._embedding_manager = get_embedding_manager()
        return self._embedding_manager
    
    @property
    def llm_manager(self) -> Optional["LLMManager"]:
        """Get LLM manager."""
        return self._llm_manager
    
    @property
    def name(self) -> str:
        """Provider name (implements BaseProvider protocol)."""
        return f"search-orchestrator:{self.default_strategy.value}"
    
    def is_available(self) -> bool:
        """Check if orchestrator is available (implements BaseProvider protocol)."""
        try:
            return self.vector_store.is_available()
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
                "default_strategy": self.default_strategy.value,
                "caching_enabled": self.cache is not None,
                "reranking_enabled": self.reranker is not None,
                "metrics": self.metrics,
            }
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
            }
    
    def search(
        self,
        query: str,
        strategy: Optional[SearchStrategy] = None,
        config: Optional[SearchConfig] = None,
        use_cache: bool = True,
        use_reranking: bool = False,
        top_k: Optional[int] = None,
        filters: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> List[SearchResult]:
        """
        Execute search with specified strategy.
        
        Args:
            query: Search query text
            strategy: Search strategy (default: self.default_strategy)
            config: Search configuration
            use_cache: Whether to use cache (if available)
            use_reranking: Whether to rerank results (if available)
            top_k: Override default top_k
            filters: Metadata filters
            **kwargs: Strategy-specific parameters
            
        Returns:
            List of search results sorted by relevance
            
        Raises:
            SearchError: If search fails
        """
        from config.settings import settings
        
        # Input validation
        if not query or not query.strip():
            logger.warning("Empty query received")
            return []
        
        query = query.strip()
        
        start_time = datetime.now()
        
        strategy = strategy or self.default_strategy
        config = config or SearchConfig()
        
        # Apply overrides
        if top_k:
            config.top_k = top_k
        elif not config.top_k:
            config.top_k = settings.SEARCH_TOP_K
        
        if filters:
            config.filters = filters
        
        # Update metrics
        self.metrics["total_searches"] += 1
        self.metrics["strategy_usage"][strategy.value] = \
            self.metrics["strategy_usage"].get(strategy.value, 0) + 1
        
        logger.info(
            f"Search request: query='{query[:50]}...', "
            f"strategy={strategy.value}, top_k={config.top_k}"
        )
        
        # Check cache
        if use_cache and self.cache:
            cache_key = self._get_cache_key(query, strategy, config)
            cached_results = self._get_from_cache(cache_key)
            
            if cached_results:
                self.metrics["cache_hits"] += 1
                logger.info("Cache hit")
                return cached_results
            
            self.metrics["cache_misses"] += 1
        
        try:
            # Create strategy instance
            search_strategy = self.factory.create(
                strategy=strategy,
                vector_store=self.vector_store,
                embedding_manager=self.embedding_manager,
                llm_manager=self.llm_manager,
                config=config
            )
            
            # Execute search
            results = search_strategy.search(
                query=query,
                top_k=config.top_k,
                filters=config.filters,
                **kwargs
            )
            
            # Re-rank if enabled
            if use_reranking and self.reranker and len(results) > 1:
                logger.info("Re-ranking results...")
                results = self.reranker.rerank(
                    query=query,
                    results=results,
                    top_k=config.top_k
                )
            
            # Cache results
            if use_cache and self.cache:
                self._save_to_cache(cache_key, results)
            
            # Update metrics
            latency_ms = (datetime.now() - start_time).total_seconds() * 1000
            self.metrics["total_latency_ms"] += latency_ms
            self.metrics["average_latency_ms"] = (
                self.metrics["total_latency_ms"] / self.metrics["total_searches"]
            )
            
            logger.info(
                f"Search complete: found={len(results)}, "
                f"latency={latency_ms:.2f}ms"
            )
            
            return results
            
        except Exception as e:
            logger.error(f"Search failed: {e}", exc_info=True)
            from src.core.exceptions import SearchError
            raise SearchError(
                f"Search failed: {e}", 
                query=query[:50], 
                strategy=strategy.value
            )
    
    def multi_strategy_search(
        self,
        query: str,
        strategies: List[SearchStrategy],
        fusion_method: str = "rrf",
        config: Optional[SearchConfig] = None,
        **kwargs
    ) -> List[SearchResult]:
        """
        Execute multiple strategies and fuse results (ensemble retrieval).
        
        Industry standard: Ensemble retrieval
        - Run multiple strategies in parallel
        - Fuse results for better recall/precision
        - More robust than single strategy
        
        Args:
            query: Search query
            strategies: List of strategies to use
            fusion_method: How to fuse results ("rrf" or "weighted")
            config: Search configuration
            **kwargs: Additional parameters
            
        Returns:
            Fused search results
        """
        config = config or SearchConfig()
        
        logger.info(
            f"Multi-strategy search: query='{query[:50]}...', "
            f"strategies={[s.value for s in strategies]}"
        )
        
        all_results = []
        
        # Execute each strategy
        for strategy in strategies:
            try:
                results = self.search(
                    query=query,
                    strategy=strategy,
                    config=config,
                    use_reranking=False,  # Rerank after fusion
                    **kwargs
                )
                all_results.append(results)
                logger.info(f"{strategy.value}: {len(results)} results")
            except Exception as e:
                logger.error(f"Strategy {strategy} failed: {e}")
                all_results.append([])
        
        # Fuse results
        if fusion_method == "rrf":
            fused_results = self._reciprocal_rank_fusion(all_results)
        else:
            logger.warning(f"Unknown fusion method: {fusion_method}, using RRF")
            fused_results = self._reciprocal_rank_fusion(all_results)
        
        # Re-rank fused results
        if self.reranker and len(fused_results) > 1:
            fused_results = self.reranker.rerank(
                query=query,
                results=fused_results,
                top_k=config.top_k
            )
        
        logger.info(f"Multi-strategy complete: fused={len(fused_results)}")
        
        return fused_results[:config.top_k]
    
    def _reciprocal_rank_fusion(
        self,
        results_list: List[List[SearchResult]],
        k: int = 60
    ) -> List[SearchResult]:
        """
        Fuse multiple result lists using Reciprocal Rank Fusion.
        
        Args:
            results_list: List of result lists from different strategies
            k: RRF constant (default: 60)
            
        Returns:
            Fused and sorted results
        """
        doc_scores: Dict[str, Dict[str, Any]] = {}
        
        for results in results_list:
            for rank, result in enumerate(results, start=1):
                doc_id = result.id
                rrf_score = 1.0 / (k + rank)
                
                if doc_id in doc_scores:
                    doc_scores[doc_id]['score'] += rrf_score
                else:
                    doc_scores[doc_id] = {
                        'result': result,
                        'score': rrf_score
                    }
        
        # Sort by RRF score
        sorted_docs = sorted(
            doc_scores.items(),
            key=lambda x: x[1]['score'],
            reverse=True
        )
        
        # Create fused results
        fused_results = []
        for doc_id, data in sorted_docs:
            result = data['result']
            result.score = data['score']
            fused_results.append(result)
        
        return fused_results
    
    def get_metrics(self) -> Dict[str, Any]:
        """
        Get performance metrics.
        
        Returns:
            Dict with search performance statistics
        """
        cache_hit_rate = 0.0
        if self.metrics["total_searches"] > 0:
            cache_hit_rate = (
                self.metrics["cache_hits"] / self.metrics["total_searches"]
            )
        
        return {
            **self.metrics,
            "cache_hit_rate": cache_hit_rate,
            "cache_enabled": self.cache is not None,
            "reranking_enabled": self.reranker is not None
        }
    
    def reset_metrics(self) -> None:
        """Reset performance metrics."""
        self.metrics = {
            "total_searches": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "strategy_usage": {},
            "average_latency_ms": 0.0,
            "total_latency_ms": 0.0
        }
        logger.info("Metrics reset")
    
    def _get_cache_key(
        self,
        query: str,
        strategy: SearchStrategy,
        config: SearchConfig
    ) -> str:
        """Generate cache key for query."""
        import hashlib
        
        key_data = f"{query}_{strategy.value}_{config.top_k}_{config.filters}"
        return hashlib.md5(key_data.encode()).hexdigest()
    
    def _get_from_cache(self, key: str) -> Optional[List[SearchResult]]:
        """Get results from cache."""
        if not self.cache:
            return None
        
        try:
            return self.cache.get(key)
        except Exception as e:
            logger.error(f"Cache get failed: {e}")
            return None
    
    def _save_to_cache(self, key: str, results: List[SearchResult]) -> None:
        """Save results to cache."""
        if not self.cache:
            return
        
        try:
            self.cache.set(key, results, ttl=3600)  # 1 hour TTL
        except Exception as e:
            logger.error(f"Cache set failed: {e}")


def get_search_orchestrator(
    vector_store: Optional["VectorDBManager"] = None,
    embedding_manager: Optional["EmbeddingManager"] = None,
    llm_manager: Optional["LLMManager"] = None,
    **kwargs
) -> SearchOrchestrator:
    """
    Get or create global search orchestrator instance.
    
    Thread-safe singleton accessor.
    
    Args:
        vector_store: Vector store instance (only used on first call)
        embedding_manager: Embedding manager (only used on first call)
        llm_manager: LLM manager (only used on first call)
        **kwargs: Additional orchestrator parameters
        
    Returns:
        SearchOrchestrator singleton instance
    """
    return SearchOrchestrator(
        vector_store=vector_store,
        embedding_manager=embedding_manager,
        llm_manager=llm_manager,
        **kwargs
    )


def reset_search_orchestrator() -> None:
    """
    Reset the search orchestrator singleton.
    
    Useful for testing or reconfiguration.
    """
    SearchOrchestrator._reset_instance()
