"""
Retrieval Quality Metrics.

Evaluates the quality of retrieved contexts:
- Context relevance to query
- Precision@K
- Mean Reciprocal Rank (MRR)
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import logging
from src.utils import get_logger
import numpy as np

from config.settings import settings

logger = get_logger(__name__)


@dataclass
class RetrievalMetrics:
    """Container for retrieval evaluation metrics."""
    context_relevance: float  # 0-1: How relevant are contexts to query
    context_precision: float  # 0-1: Precision at K
    context_recall: float     # 0-1: Recall estimate
    mrr: float               # Mean Reciprocal Rank
    average_score: float     # Average similarity score
    
    def to_dict(self) -> Dict[str, float]:
        return {
            'context_relevance': self.context_relevance,
            'context_precision': self.context_precision,
            'context_recall': self.context_recall,
            'mrr': self.mrr,
            'average_score': self.average_score,
        }


class RetrievalEvaluator:
    """
    Evaluate retrieval quality using heuristic methods.
    
    Uses embedding similarity and keyword overlap to assess
    how well retrieved contexts match the query.
    """
    
    def __init__(
        self,
        embedding_manager=None,
        relevance_threshold: float = 0.5,
    ):
        """
        Initialize retrieval evaluator.
        
        Args:
            embedding_manager: Embedding manager for similarity computation
            relevance_threshold: Minimum score to consider a context relevant
        """
        self.embedding_manager = embedding_manager
        self.relevance_threshold = relevance_threshold
        
        if self.embedding_manager is None:
            try:
                from src.infrastructure.embeddings.manager import get_embedding_manager
                self.embedding_manager = get_embedding_manager()
            except Exception as e:
                logger.warning(f"Could not load embedding manager: {e}")
    
    def evaluate(
        self,
        query: str,
        contexts: List[str],
        scores: Optional[List[float]] = None,
    ) -> RetrievalMetrics:
        """
        Evaluate retrieval quality.
        
        Args:
            query: Original query
            contexts: List of retrieved context strings
            scores: Optional list of similarity scores from retrieval
            
        Returns:
            RetrievalMetrics with all computed metrics
        """
        if not contexts:
            return RetrievalMetrics(
                context_relevance=0.0,
                context_precision=0.0,
                context_recall=0.0,
                mrr=0.0,
                average_score=0.0,
            )
        
        # If scores provided, use them; otherwise compute
        if scores is None:
            scores = self._compute_similarity_scores(query, contexts)
        
        # Compute metrics
        context_relevance = self._compute_context_relevance(query, contexts, scores)
        context_precision = self._compute_precision(scores)
        context_recall = self._estimate_recall(scores)
        mrr = self._compute_mrr(scores)
        average_score = np.mean(scores) if scores else 0.0
        
        return RetrievalMetrics(
            context_relevance=context_relevance,
            context_precision=context_precision,
            context_recall=context_recall,
            mrr=mrr,
            average_score=float(average_score),
        )
    
    def _compute_similarity_scores(
        self,
        query: str,
        contexts: List[str],
    ) -> List[float]:
        """Compute semantic similarity between query and each context."""
        if self.embedding_manager is None:
            # Fallback to keyword overlap
            return self._keyword_overlap_scores(query, contexts)
        
        try:
            query_embedding = self.embedding_manager.generate_embedding(query)
            context_embeddings = [
                self.embedding_manager.generate_embedding(ctx)
                for ctx in contexts
            ]
            
            # Compute cosine similarity
            scores = []
            for ctx_emb in context_embeddings:
                similarity = self._cosine_similarity(query_embedding, ctx_emb)
                scores.append(similarity)
            
            return scores
            
        except Exception as e:
            logger.warning(f"Embedding similarity failed: {e}, using keyword overlap")
            return self._keyword_overlap_scores(query, contexts)
    
    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """Compute cosine similarity between two vectors."""
        vec1 = np.array(vec1)
        vec2 = np.array(vec2)
        
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        return float(np.dot(vec1, vec2) / (norm1 * norm2))
    
    def _keyword_overlap_scores(
        self,
        query: str,
        contexts: List[str],
    ) -> List[float]:
        """Compute keyword overlap as fallback similarity metric."""
        query_words = set(query.lower().split())
        
        scores = []
        for context in contexts:
            context_words = set(context.lower().split())
            
            if not query_words:
                scores.append(0.0)
                continue
            
            overlap = len(query_words & context_words)
            score = overlap / len(query_words)
            scores.append(min(score, 1.0))
        
        return scores
    
    def _compute_context_relevance(
        self,
        query: str,
        contexts: List[str],
        scores: List[float],
    ) -> float:
        """
        Compute overall context relevance score.
        
        Combines semantic similarity with keyword presence.
        """
        if not contexts:
            return 0.0
        
        # Weight by position (earlier contexts matter more)
        position_weights = [1.0 / (i + 1) for i in range(len(contexts))]
        total_weight = sum(position_weights)
        
        weighted_score = sum(
            score * weight 
            for score, weight in zip(scores, position_weights)
        ) / total_weight
        
        # Check for key financial terms from query in contexts
        financial_terms = self._extract_financial_terms(query)
        term_coverage = self._compute_term_coverage(financial_terms, contexts)
        
        # Combine semantic and term coverage
        relevance = 0.7 * weighted_score + 0.3 * term_coverage
        
        return min(relevance, 1.0)
    
    def _extract_financial_terms(self, text: str) -> List[str]:
        """Extract financial terms from text."""
        financial_keywords = [
            'revenue', 'income', 'profit', 'loss', 'assets', 'liabilities',
            'equity', 'cash', 'flow', 'balance', 'sheet', 'statement',
            'earnings', 'eps', 'margin', 'growth', 'ratio', 'debt',
            'quarter', 'annual', 'fiscal', 'year', 'q1', 'q2', 'q3', 'q4',
        ]
        
        text_lower = text.lower()
        return [term for term in financial_keywords if term in text_lower]
    
    def _compute_term_coverage(
        self,
        terms: List[str],
        contexts: List[str],
    ) -> float:
        """Compute what fraction of key terms appear in contexts."""
        if not terms:
            return 1.0  # No specific terms to check
        
        combined_context = ' '.join(contexts).lower()
        found = sum(1 for term in terms if term in combined_context)
        
        return found / len(terms)
    
    def _compute_precision(self, scores: List[float]) -> float:
        """Compute precision - fraction of retrieved docs above threshold."""
        if not scores:
            return 0.0
        
        relevant = sum(1 for s in scores if s >= self.relevance_threshold)
        return relevant / len(scores)
    
    def _estimate_recall(self, scores: List[float]) -> float:
        """
        Estimate recall based on score distribution.
        
        Higher average scores suggest better coverage.
        This is an estimate since we don't have ground truth.
        """
        if not scores:
            return 0.0
        
        # Use average score as recall proxy
        avg_score = np.mean(scores)
        
        # Boost if we have high-scoring results
        high_score_count = sum(1 for s in scores if s >= 0.7)
        high_score_bonus = min(high_score_count * 0.1, 0.3)
        
        return min(avg_score + high_score_bonus, 1.0)
    
    def _compute_mrr(self, scores: List[float]) -> float:
        """
        Compute Mean Reciprocal Rank.
        
        MRR = 1 / position of first relevant result.
        """
        if not scores:
            return 0.0
        
        for i, score in enumerate(scores):
            if score >= self.relevance_threshold:
                return 1.0 / (i + 1)
        
        return 0.0  # No relevant results


# Global instance
_retrieval_evaluator: Optional[RetrievalEvaluator] = None


def get_retrieval_evaluator() -> RetrievalEvaluator:
    """Get or create global retrieval evaluator."""
    global _retrieval_evaluator
    if _retrieval_evaluator is None:
        _retrieval_evaluator = RetrievalEvaluator()
    return _retrieval_evaluator
