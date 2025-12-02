"""
Linear combination fusion algorithm.

Simple linear combination of raw scores without normalization.
Assumes scores are already comparable.
"""

from typing import List

from src.retrieval.search.base import SearchResult


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
