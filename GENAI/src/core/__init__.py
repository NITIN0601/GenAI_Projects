"""
Core module - Shared kernel for GENAI RAG system.

This module contains cross-cutting concerns used throughout the application:
- Path management (cross-platform)
- Deduplication (content-hash based)
- Exception hierarchy
- Interface definitions (protocols)
"""

from src.core.paths import PathManager, get_paths
from src.core.deduplication import PDFDeduplicator, get_deduplicator
from src.core.exceptions import (
    GENAIException,
    ExtractionError,
    EmbeddingError,
    VectorStoreError,
    LLMError,
    RAGError,
    CacheError,
    ValidationError,
)

__all__ = [
    # Paths
    'PathManager',
    'get_paths',
    # Deduplication
    'PDFDeduplicator',
    'get_deduplicator',
    # Exceptions
    'GENAIException',
    'ExtractionError',
    'EmbeddingError',
    'VectorStoreError',
    'LLMError',
    'RAGError',
    'CacheError',
    'ValidationError',
]
