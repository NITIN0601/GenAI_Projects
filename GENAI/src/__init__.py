"""
GENAI RAG System - Source Package

Enterprise-level RAG system for financial document processing.

Main modules:
- core: Shared kernel (paths, deduplication, exceptions, interfaces)
- extraction: PDF extraction with multiple backends
- embeddings: Embedding generation with multiple providers
- vector_store: Vector database management
- retrieval: Query processing and retrieval
- llm: LLM integration and management
- rag: End-to-end RAG pipeline
- evaluation: RAG quality evaluation
- guardrails: Input/output safety
- cache: Caching layer
- utils: Shared utilities
"""

__version__ = "2.1.0"
__author__ = "GENAI Team"

__all__ = [
    'core',
    'domain',
    'infrastructure',
    'application',
    'extraction',
    'embeddings',
    'vector_store',
    'retrieval',
    'llm',
    'rag',
    'prompts',
    'models',
    'pipeline',
    'scheduler',
    'cache',
    'utils',
    'evaluation',
    'guardrails',
]

