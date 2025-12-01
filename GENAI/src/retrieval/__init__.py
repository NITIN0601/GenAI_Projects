"""
Retrieval module.

Handles query processing, retrieval, and reranking.

Example:
    >>> from src.retrieval import Retriever, QueryProcessor
    >>> retriever = Retriever(vector_store=store)
    >>> results = retriever.retrieve(query="financial data")
"""

from src.retrieval.retriever import Retriever, get_retriever
from src.retrieval.query_processor import QueryProcessor, get_query_processor

__version__ = "2.0.0"

__all__ = [
    'Retriever',
    'get_retriever',
    'QueryProcessor',
    'get_query_processor',
]
