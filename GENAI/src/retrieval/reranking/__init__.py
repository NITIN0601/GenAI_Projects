"""
Reranking package.

Provides cross-encoder reranking for improving search result quality.

Two-stage retrieval (industry standard):
1. First stage: Fast retrieval (vector/hybrid) - high recall
2. Second stage: Slow re-ranking (cross-encoder) - high precision

Usage:
    from src.retrieval.reranking import CrossEncoderReranker
    
    reranker = CrossEncoderReranker(model_name='cross-encoder/ms-marco-MiniLM-L-6-v2')
    reranked = reranker.rerank(query="question", results=search_results)
"""

from src.retrieval.reranking.cross_encoder import CrossEncoderReranker, get_reranker

__all__ = [
    'CrossEncoderReranker',
    'get_reranker',
]
