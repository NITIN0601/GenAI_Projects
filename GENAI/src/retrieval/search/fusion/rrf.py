"""
Reciprocal Rank Fusion (RRF) algorithm.

RRF is a simple but effective fusion method that doesn't require
score normalization. It's robust to outliers and works well in practice.

Reference: "Reciprocal Rank Fusion outperforms Condorcet and
individual Rank Learning Methods" (Cormack et al., 2009)
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
