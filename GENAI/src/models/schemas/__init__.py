"""
Models - Schemas module.

DEPRECATION NOTICE:
    This module is maintained for backward compatibility.
    New code should import directly from src.domain:
    
        from src.domain import TableMetadata, TableChunk, RAGQuery, RAGResponse
    
    All schemas are now in src.domain (single source of truth).
"""

# Import core schemas from domain layer (single source of truth)
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

from src.domain.queries import (
    RAGQuery,
    RAGResponse,
    SearchResult,
)

from src.domain.documents import (
    DocumentMetadata,
    PageLayout,
    Period,
    DocumentProcessingResult,
)

__all__ = [
    # Core schemas (from domain layer)
    "TableMetadata",
    "TableChunk",
    "FinancialTable",
    "RAGQuery",
    "RAGResponse",
    "DocumentProcessingResult",
    "SearchResult",
    "DocumentMetadata",
    "PageLayout",
    "Period",
    # Enhanced schemas (now also from domain layer)
    "ColumnHeader",
    "RowHeader",
    "DataCell",
    "Footnote",
    "EnhancedFinancialTable",
    "EnhancedDocument",
    "ProcessingQueueItem",
]

