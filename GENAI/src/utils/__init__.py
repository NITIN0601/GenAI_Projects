"""
Utility modules for GENAI RAG system.

Provides:
- Centralized logging configuration
- Custom exceptions (re-exported from core)
- Metrics and monitoring
- Helper functions
- Cleanup utilities

Note: Tracing/observability is now in src.infrastructure.observability
"""

from src.utils.logger import get_logger, setup_logging
from src.core.exceptions import (
    GENAIException,
    ExtractionError,
    EmbeddingError,
    VectorStoreError,
    LLMError,
    RAGError
)
from src.utils.helpers import (
    compute_file_hash,
    get_pdf_files,
    ensure_directory,
    format_number,
    truncate_text
)
from src.utils.cleanup import (
    clear_all_cache,
    clear_pycache,
    clear_application_cache,
    quick_clean,
    full_clean
)

# Re-export tracing from infrastructure for convenience
from src.infrastructure.observability import (
    setup_tracing,
    is_tracing_enabled,
    traceable_function,
    get_tracing_callbacks,
)

__all__ = [
    'get_logger',
    'setup_logging',
    'GENAIException',
    'ExtractionError',
    'EmbeddingError',
    'VectorStoreError',
    'LLMError',
    'RAGError',
    'compute_file_hash',
    'get_pdf_files',
    'ensure_directory',
    'format_number',
    'truncate_text',
    # Cleanup utilities
    'clear_all_cache',
    'clear_pycache',
    'clear_application_cache',
    'quick_clean',
    'full_clean',
    # Tracing (re-exported from infrastructure.observability)
    'setup_tracing',
    'is_tracing_enabled',
    'traceable_function',
    'get_tracing_callbacks',
]
