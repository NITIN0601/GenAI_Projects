"""
Weighted score fusion algorithm.

Normalizes scores from each retriever to [0, 1] and combines
them using weighted average.
"""

from typing import List
import logging
from src.utils import get_logger

from src.retrieval.search.base import SearchResult

logger = get_logger(__name__)


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
