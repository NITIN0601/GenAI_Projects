"""
Search strategies package.

Available strategies:
- VectorSearchStrategy: Semantic similarity search
- KeywordSearchStrategy: BM25 keyword search  
- HybridSearchStrategy: Vector + Keyword fusion (RECOMMENDED)
- HyDESearchStrategy: Hypothetical Document Embeddings
- MultiQuerySearchStrategy: Query expansion

Usage:
    from src.retrieval.search.strategies import HybridSearchStrategy
    
    strategy = HybridSearchStrategy(vector_store, embedding_manager)
    results = strategy.search(query="financial data", top_k=5)
"""

from src.retrieval.search.strategies.vector_search import VectorSearchStrategy
from src.retrieval.search.strategies.keyword_search import KeywordSearchStrategy
from src.retrieval.search.strategies.hybrid_search import HybridSearchStrategy
from src.retrieval.search.strategies.hyde_search import HyDESearchStrategy
from src.retrieval.search.strategies.multi_query_search import MultiQuerySearchStrategy

__all__ = [
    'VectorSearchStrategy',
    'KeywordSearchStrategy',
    'HybridSearchStrategy',
    'HyDESearchStrategy',
    'MultiQuerySearchStrategy',
]
