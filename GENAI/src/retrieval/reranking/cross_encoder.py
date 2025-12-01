"""
Cross-Encoder Re-ranker for improving search precision.

Industry standard: Two-stage retrieval
1. First stage: Fast retrieval (vector/hybrid) - high recall
2. Second stage: Slow re-ranking (cross-encoder) - high precision

Cross-encoders are more accurate than bi-encoders but slower.
Use for final ranking of top-k results.

Reference: sentence-transformers cross-encoders
"""

from typing import List, Optional
import logging

from sentence_transformers import CrossEncoder
import numpy as np

from src.retrieval.search.base import SearchResult

logger = logging.getLogger(__name__)


class CrossEncoderReranker:
    """
    Re-rank search results using cross-encoder model.
    
    How it works:
    1. Take top-N results from initial search
    2. Score each (query, document) pair with cross-encoder
    3. Re-sort by cross-encoder scores
    4. Return top-K re-ranked results
    
    Why it's better:
    - Cross-encoder sees query and document together
    - More accurate than bi-encoder (embedding) similarity
    - Better at nuanced relevance judgments
    
    Trade-off:
    - Much slower than bi-encoder
    - Use only for final re-ranking of small result set
    
    Recommended usage:
    - Retrieve 20-50 results with fast search
    - Re-rank to get best 5-10 results
    """
    
    def __init__(
        self,
        model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2",
        batch_size: int = 32
    ):
        """
        Initialize cross-encoder re-ranker.
        
        Args:
            model_name: Cross-encoder model name
            batch_size: Batch size for inference
        """
        self.model_name = model_name
        self.batch_size = batch_size
        self.model = None
        
        # Lazy load model
        self._load_model()
    
    def _load_model(self):
        """Load cross-encoder model."""
        try:
            logger.info(f"Loading cross-encoder model: {self.model_name}")
            self.model = CrossEncoder(self.model_name)
            logger.info("Cross-encoder model loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load cross-encoder model: {e}")
            self.model = None
    
    def rerank(
        self,
        query: str,
        results: List[SearchResult],
        top_k: Optional[int] = None
    ) -> List[SearchResult]:
        """
        Re-rank search results using cross-encoder.
        
        Args:
            query: Search query
            results: Initial search results to re-rank
            top_k: Number of top results to return (default: all)
            
        Returns:
            Re-ranked search results
        """
        if not self.model:
            logger.warning("Cross-encoder model not available, skipping re-ranking")
            return results
        
        if not results:
            return results
        
        logger.info(f"Re-ranking {len(results)} results...")
        
        try:
            # Prepare (query, document) pairs
            pairs = [(query, result.content) for result in results]
            
            # Get cross-encoder scores
            scores = self.model.predict(
                pairs,
                batch_size=self.batch_size,
                show_progress_bar=False
            )
            
            # Update results with rerank scores
            for result, score in zip(results, scores):
                result.rerank_score = float(score)
            
            # Sort by rerank score
            reranked_results = sorted(
                results,
                key=lambda x: x.rerank_score,
                reverse=True
            )
            
            logger.info(f"Re-ranking complete")
            
            # Return top-k if specified
            if top_k:
                return reranked_results[:top_k]
            
            return reranked_results
            
        except Exception as e:
            logger.error(f"Re-ranking failed: {e}", exc_info=True)
            return results
    
    def get_model_info(self) -> dict:
        """Get model information."""
        return {
            "model_name": self.model_name,
            "batch_size": self.batch_size,
            "loaded": self.model is not None
        }


# Global reranker instance
_reranker: Optional[CrossEncoderReranker] = None


def get_reranker(
    model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
) -> CrossEncoderReranker:
    """Get or create global reranker instance."""
    global _reranker
    
    if _reranker is None:
        _reranker = CrossEncoderReranker(model_name=model_name)
    
    return _reranker
