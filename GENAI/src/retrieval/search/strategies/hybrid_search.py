"""Hybrid search strategy."""

from typing import List, Dict, Any, Optional
import logging
from src.utils import get_logger

from src.retrieval.search.base import BaseSearchStrategy, SearchResult
from src.retrieval.search.strategies.vector_search import VectorSearchStrategy
from src.retrieval.search.strategies.keyword_search import KeywordSearchStrategy
from src.retrieval.search.fusion import reciprocal_rank_fusion, weighted_score_fusion

logger = get_logger(__name__)


class HybridSearchStrategy(BaseSearchStrategy):
    """Hybrid search combining vector and keyword search."""
    
    # Sub-strategies (not Pydantic fields, internal use)
    _vector_strategy: Optional[VectorSearchStrategy] = None
    _keyword_strategy: Optional[KeywordSearchStrategy] = None
    
    def __init__(self, **kwargs):
        """Initialize hybrid search."""
        super().__init__(**kwargs)
        
        if not self.embedding_manager:
            raise ValueError("Hybrid search requires embedding_manager")
            
        # Initialize sub-strategies
        # We pass the same config and components
        self._vector_strategy = VectorSearchStrategy(
            vector_store=self.vector_store,
            embedding_manager=self.embedding_manager,
            llm_manager=self.llm_manager,
            config=self.config
        )
        
        self._keyword_strategy = KeywordSearchStrategy(
            vector_store=self.vector_store,
            embedding_manager=self.embedding_manager,
            llm_manager=self.llm_manager,
            config=self.config
        )
    
    def search(
        self,
        query: str,
        top_k: Optional[int] = None,
        filters: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> List[SearchResult]:
        """Execute hybrid search."""
        top_k = top_k or self.config.top_k
        filters = filters or self.config.filters
        
        try:
            # Execute both searches
            vector_results = self._vector_strategy.search(
                query, top_k=top_k * 2, filters=filters
            )
            
            keyword_results = self._keyword_strategy.search(
                query, top_k=top_k * 2, filters=filters
            )
            
            # Fuse results
            weights = self.config.hybrid_weights or {"vector": 0.6, "keyword": 0.4}
            weight_list = [weights.get("vector", 0.6), weights.get("keyword", 0.4)]
            
            if self.config.hybrid_fusion_method == "weighted":
                fused_results = weighted_score_fusion(
                    [vector_results, keyword_results],
                    weights=weight_list
                )
            else:
                fused_results = reciprocal_rank_fusion(
                    [vector_results, keyword_results],
                    weights=weight_list
                )
            
            return fused_results[:top_k]
            
        except Exception as e:
            logger.error(f"Hybrid search failed: {e}")
            return []
    
    def get_strategy_name(self) -> str:
        return "hybrid"
