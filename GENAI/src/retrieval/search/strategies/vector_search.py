"""Vector search strategy."""

from typing import List, Dict, Any, Optional
import logging
from src.utils import get_logger

from src.retrieval.search.base import BaseSearchStrategy, SearchResult

logger = get_logger(__name__)


class VectorSearchStrategy(BaseSearchStrategy):
    """Vector search using semantic embeddings."""
    
    def __init__(self, **kwargs):
        """Initialize vector search."""
        super().__init__(**kwargs)
        
        if not self.embedding_manager:
            raise ValueError("Vector search requires embedding_manager")
    
    def search(
        self,
        query: str,
        top_k: Optional[int] = None,
        filters: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> List[SearchResult]:
        """Execute vector search."""
        top_k = top_k or self.config.top_k
        filters = filters or self.config.filters
        
        try:
            # Generate embedding
            query_embedding = self.embedding_manager.generate_embedding(query)
            
            # Search vector store
            raw_results = self.vector_store.search(
                query_embedding=query_embedding,
                top_k=top_k,
                filters=filters
            )
            
            # Convert results
            search_results = self._convert_to_search_results(
                raw_results,
                strategy_name="vector"
            )
            
            # Filter by threshold
            filtered_results = [
                r for r in search_results
                if r.score >= self.config.similarity_threshold
            ]
            
            return filtered_results[:top_k]
            
        except Exception as e:
            logger.error(f"Vector search failed: {e}")
            return []
    
    def get_strategy_name(self) -> str:
        return "vector"
