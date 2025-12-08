"""
Core module - Shared kernel for GENAI RAG system.

This module contains cross-cutting concerns used throughout the application:
- Path management (cross-platform)
- Deduplication (content-hash based)
- Exception hierarchy
- Interface definitions (protocols)
- Singleton pattern (thread-safe)
- Provider registry (abstract factory)
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
    PipelineError,
    SearchError,
    CacheError,
    ValidationError,
)
from src.core.singleton import (
    ThreadSafeSingleton,
    get_or_create_singleton,
    reset_all_singletons,
)
from src.core.registry import (
    ProviderRegistry,
    ProviderNotRegisteredError,
    create_llm_registry,
    create_vectordb_registry,
    create_embedding_registry,
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
    'PipelineError',
    'SearchError',
    'CacheError',
    'ValidationError',
    # Singleton
    'ThreadSafeSingleton',
    'get_or_create_singleton',
    'reset_all_singletons',
    # Registry
    'ProviderRegistry',
    'ProviderNotRegisteredError',
    'create_llm_registry',
    'create_vectordb_registry',
    'create_embedding_registry',
]

