"""
RAG Pipeline Module

Provides end-to-end RAG query processing:
1. Query processing and understanding
2. Context retrieval from vector DB
3. LLM generation with retrieved context
4. Response formatting and export
"""

from src.rag.pipeline import QueryEngine, get_query_engine
from src.rag.exporter import RAGExporter

__version__ = "2.0.0"

__all__ = [
    "QueryEngine",
    "get_query_engine",
    "RAGExporter",
]
