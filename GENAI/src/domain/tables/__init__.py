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

__all__ = [
    'TableMetadata',
    'TableChunk',
    'FinancialTable',
]
