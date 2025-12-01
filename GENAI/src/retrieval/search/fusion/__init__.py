"""
Fusion algorithms for combining search results.

Industry standard: Result fusion
- Reciprocal Rank Fusion (RRF)
- Weighted score fusion
- Linear combination

Used by hybrid search, multi-query, and ensemble retrieval.
"""

from typing import List, Optional
import logging

from src.retrieval.search.base import SearchResult

logger = logging.getLogger(__name__)


def reciprocal_rank_fusion(
    results_list: List[List[SearchResult]],
    weights: Optional[List[float]] = None,
    k: int = 60
) -> List[SearchResult]:
    """
    Fuse multiple result lists using Reciprocal Rank Fusion (RRF).
    
    RRF is a simple but effective fusion method that doesn't require
    score normalization. It's robust to outliers and works well in practice.
    
    Formula: score(d) = Σ(weight_i / (k + rank_i(d)))
    
    Reference: "Reciprocal Rank Fusion outperforms Condorcet and
    individual Rank Learning Methods" (Cormack et al., 2009)
    
    Args:
        results_list: List of ranked result lists from different retrievers
        weights: Weight for each result list (default: equal weights)
        k: RRF constant, typically 60 (default: 60)
        
    Returns:
        Fused and re-ranked results
        
    Example:
        # Fuse vector and keyword results
        fused = reciprocal_rank_fusion(
            [vector_results, keyword_results],
            weights=[0.6, 0.4],
            k=60
        )
    """
    if not results_list:
        return []
    
    # Default to equal weights if not specified
    if weights is None:
        weights = [1.0] * len(results_list)
    
    if len(weights) != len(results_list):
        logger.warning(
            f"Weights length ({len(weights)}) doesn't match "
            f"results_list length ({len(results_list)}). Using equal weights."
        )
        weights = [1.0] * len(results_list)
    
    # Collect all unique documents with their RRF scores
    doc_scores = {}
    
    for weight, results in zip(weights, results_list):
        for rank, result in enumerate(results, start=1):
            doc_id = result.id
            
            # RRF score contribution from this ranking
            rrf_score = weight / (k + rank)
            
            if doc_id in doc_scores:
                doc_scores[doc_id]['score'] += rrf_score
                doc_scores[doc_id]['appearances'] += 1
            else:
                doc_scores[doc_id] = {
                    'result': result,
                    'score': rrf_score,
                    'appearances': 1
                }
    
    # Sort by RRF score
    sorted_docs = sorted(
        doc_scores.items(),
        key=lambda x: x[1]['score'],
        reverse=True
    )
    
    # Create fused results with updated scores
    fused_results = []
    for doc_id, data in sorted_docs:
        result = data['result']
        result.score = data['score']
        # Add metadata about fusion
        result.metadata['rrf_score'] = data['score']
        result.metadata['appearances'] = data['appearances']
        fused_results.append(result)
    
    logger.debug(
        f"RRF fusion: {len(results_list)} lists → "
        f"{len(fused_results)} unique results"
    )
    
    return fused_results


def weighted_score_fusion(
    results_list: List[List[SearchResult]],
    weights: List[float]
) -> List[SearchResult]:
    """
    Fuse results using weighted score combination.
    
    Normalizes scores from each retriever to [0, 1] and combines
    them using weighted average.
    
    Formula: score(d) = Σ(weight_i * normalized_score_i(d))
    
    Args:
        results_list: List of ranked result lists
        weights: Weight for each result list (must sum to 1.0)
        
    Returns:
        Fused and re-ranked results
        
    Example:
        # Fuse with custom weights
        fused = weighted_score_fusion(
            [vector_results, keyword_results],
            weights=[0.7, 0.3]
        )
    """
    if not results_list:
        return []
    
    if len(weights) != len(results_list):
        raise ValueError(
            f"Weights length ({len(weights)}) must match "
            f"results_list length ({len(results_list)})"
        )
    
    # Validate weights sum to ~1.0
    weight_sum = sum(weights)
    if not (0.99 <= weight_sum <= 1.01):
        logger.warning(
            f"Weights sum to {weight_sum:.3f}, not 1.0. "
            f"Normalizing weights."
        )
        weights = [w / weight_sum for w in weights]
    
    doc_scores = {}
    
    for weight, results in zip(weights, results_list):
        if not results:
            continue
        
        # Normalize scores to [0, 1]
        max_score = max(r.score for r in results) if results else 1.0
        min_score = min(r.score for r in results) if results else 0.0
        score_range = max_score - min_score if max_score > min_score else 1.0
        
        for result in results:
            doc_id = result.id
            
            # Normalize score
            normalized_score = (result.score - min_score) / score_range
            weighted_score = weight * normalized_score
            
            if doc_id in doc_scores:
                doc_scores[doc_id]['score'] += weighted_score
            else:
                doc_scores[doc_id] = {
                    'result': result,
                    'score': weighted_score
                }
    
    # Sort by weighted score
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
        result.metadata['weighted_score'] = data['score']
        fused_results.append(result)
    
    logger.debug(
        f"Weighted fusion: {len(results_list)} lists → "
        f"{len(fused_results)} unique results"
    )
    
    return fused_results


def linear_combination_fusion(
    results_list: List[List[SearchResult]],
    weights: List[float]
) -> List[SearchResult]:
    """
    Fuse results using simple linear combination of raw scores.
    
    No normalization - assumes scores are already comparable.
    
    Formula: score(d) = Σ(weight_i * score_i(d))
    
    Args:
        results_list: List of ranked result lists
        weights: Weight for each result list
        
    Returns:
        Fused and re-ranked results
    """
    if not results_list:
        return []
    
    doc_scores = {}
    
    for weight, results in zip(weights, results_list):
        for result in results:
            doc_id = result.id
            weighted_score = weight * result.score
            
            if doc_id in doc_scores:
                doc_scores[doc_id]['score'] += weighted_score
            else:
                doc_scores[doc_id] = {
                    'result': result,
                    'score': weighted_score
                }
    
    # Sort by combined score
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


__all__ = [
    'reciprocal_rank_fusion',
    'weighted_score_fusion',
    'linear_combination_fusion'
]
