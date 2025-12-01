"""
GENAI RAG System - Source Package

Enterprise-level RAG system for financial document processing.

Main modules:
- extraction: PDF extraction with multiple backends
- embeddings: Embedding generation with multiple providers
- vector_store: Vector database management
- retrieval: Query processing and retrieval
- llm: LLM integration and management
- rag: End-to-end RAG pipeline
- ingestion: Document ingestion and scraping
- cache: Caching layer
- utils: Shared utilities
"""

__version__ = "2.0.0"
__author__ = "GENAI Team"

__all__ = [
    'extraction',
    'embeddings',
    'vector_store',
    'retrieval',
    'llm',
    'rag',
    'ingestion',
    'cache',
    'utils'
]
