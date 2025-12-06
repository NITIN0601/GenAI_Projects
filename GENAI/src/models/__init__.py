"""
Data models for the RAG system.

DEPRECATION NOTICE:
    This module is maintained for backward compatibility.
    New code should import from src.domain instead:
    
        from src.domain import TableMetadata, RAGQuery, RAGResponse
    
    This module will be removed in version 3.0.0.
"""

import warnings

# Show deprecation warning on first import
warnings.warn(
    "Importing from src.models is deprecated. "
    "Use 'from src.domain import TableMetadata, RAGQuery, etc.' instead. "
    "This will be removed in version 3.0.0.",
    DeprecationWarning,
    stacklevel=2
)

# Import from new domain layer for backward compatibility
from src.domain.tables import (
    TableMetadata,
    TableChunk,
    FinancialTable,
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

# Import enhanced schemas that haven't been migrated yet
from src.models.schemas.enhanced_schemas import (
    ColumnHeader,
    RowHeader,
    DataCell,
    Footnote,
    EnhancedFinancialTable,
    EnhancedDocument,
    ProcessingQueueItem
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
    # Enhanced (still from models.schemas)
    'ColumnHeader',
    'RowHeader',
    'DataCell',
    'Footnote',
    'EnhancedFinancialTable',
    'EnhancedDocument',
    'ProcessingQueueItem'
]

