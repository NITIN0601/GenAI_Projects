"""
Data models for the RAG system.

DEPRECATED: This module is maintained for backward compatibility only.
Please update your imports to use src.domain directly:

    # Old (deprecated):
    from src.models import TableMetadata
    
    # New (preferred):
    from src.domain import TableMetadata, RAGQuery, RAGResponse

All models are defined in src.domain (single source of truth).
"""

import warnings
warnings.warn(
    "src.models is deprecated. Use src.domain instead: "
    "from src.domain import TableMetadata, RAGQuery, RAGResponse",
    DeprecationWarning,
    stacklevel=2
)

# Re-export from domain layer (single source of truth)
from src.domain.tables import (
    TableMetadata,
    TableChunk,
    FinancialTable,
    # Enhanced entities (now in domain)
    ColumnHeader,
    RowHeader,
    DataCell,
    Footnote,
    EnhancedFinancialTable,
    EnhancedDocument,
    ProcessingQueueItem,
)

from src.domain.documents import (
    DocumentMetadata,
    PageLayout,
    Period,
    DocumentProcessingResult,
)

from src.domain.queries import (
    RAGQuery,
    RAGResponse,
    SearchResult,
)

__all__ = [
    # Core (from domain layer)
    'TableMetadata',
    'TableChunk',
    'FinancialTable',
    'RAGQuery',
    'RAGResponse',
    'SearchResult',
    'DocumentProcessingResult',
    'DocumentMetadata',
    'PageLayout',
    'Period',
    # Enhanced (from domain.tables)
    'ColumnHeader',
    'RowHeader',
    'DataCell',
    'Footnote',
    'EnhancedFinancialTable',
    'EnhancedDocument',
    'ProcessingQueueItem',
]

