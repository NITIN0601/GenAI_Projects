"""
Table domain entities.

Contains entities for extracted financial tables and their metadata.
These are the core business objects for the RAG system.
"""

from src.domain.tables.entities import (
    TableMetadata,
    TableChunk,
    FinancialTable,
)

from src.domain.tables.enhanced import (
    ColumnHeader,
    RowHeader,
    DataCell,
    Footnote,
    EnhancedFinancialTable,
    EnhancedDocument,
    ProcessingQueueItem,
)

__all__ = [
    # Core entities
    'TableMetadata',
    'TableChunk',
    'FinancialTable',
    # Enhanced entities
    'ColumnHeader',
    'RowHeader',
    'DataCell',
    'Footnote',
    'EnhancedFinancialTable',
    'EnhancedDocument',
    'ProcessingQueueItem',
]

