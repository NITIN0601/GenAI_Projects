"""
Fusion algorithms for combining search results.

Industry standard result fusion methods:
- Reciprocal Rank Fusion (RRF) - Robust, no normalization needed
- Weighted Score Fusion - Normalized weighted averaging
- Linear Combination - Simple weighted sum

Used by hybrid search, multi-query, and ensemble retrieval.
"""

from src.retrieval.search.fusion.rrf import reciprocal_rank_fusion
from src.retrieval.search.fusion.weighted import weighted_score_fusion
from src.retrieval.search.fusion.linear import linear_combination_fusion

__all__ = [
    'reciprocal_rank_fusion',
    'weighted_score_fusion',
    'linear_combination_fusion'
]
