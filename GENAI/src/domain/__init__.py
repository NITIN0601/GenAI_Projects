"""
Domain layer - Business entities and value objects.

This module contains domain models organized by bounded context:
- tables: Financial table entities (TableMetadata, TableChunk, Enhanced*)
- documents: Document processing entities (DocumentMetadata, PageLayout)
- queries: RAG query/response entities (RAGQuery, RAGResponse, SearchResult)

All entities are re-exported for easy import.
"""

# Re-export from submodules for convenience
from src.domain.tables import (
    TableMetadata,
    TableChunk,
    FinancialTable,
    # Enhanced entities
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
    # Tables - Core
    'TableMetadata',
    'TableChunk',
    'FinancialTable',
    # Tables - Enhanced
    'ColumnHeader',
    'RowHeader',
    'DataCell',
    'Footnote',
    'EnhancedFinancialTable',
    'EnhancedDocument',
    'ProcessingQueueItem',
    # Documents
    'DocumentMetadata',
    'PageLayout',
    'Period',
    'DocumentProcessingResult',
    # Queries
    'RAGQuery',
    'RAGResponse',
    'SearchResult',
]

