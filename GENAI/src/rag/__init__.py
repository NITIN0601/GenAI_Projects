"""
RAG pipeline module.

End-to-end RAG pipeline orchestration.

Example:
    >>> from src.rag import RAGPipeline
    >>> pipeline = RAGPipeline()
    >>> response = pipeline.query("What are the financial results?")
"""

from src.rag.pipeline import QueryEngine as RAGPipeline, get_query_engine as get_rag_pipeline

__version__ = "2.0.0"

__all__ = [
    'RAGPipeline',
    'get_rag_pipeline',
]
