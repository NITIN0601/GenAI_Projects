"""
Data models for the RAG system.

This module re-exports from src.domain for convenience.
The primary definitions are in src.domain (single source of truth).

Recommended import pattern:
    from src.domain import TableMetadata, RAGQuery, RAGResponse
    
Or for convenience:
    from src.models import TableMetadata  # Same as src.domain
"""

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

