"""
VectorDB schemas - Data models for vector database.

Exports:
- TableChunk: Chunk of table data with embedding
- TableMetadata/EnhancedTableMetadata: Table metadata (21+ fields)
- VectorDBStats: Database statistics
"""

# Import from the base schemas file
from vectordb.schemas.base import (
    TableChunk,
    TableMetadata,
    EnhancedTableMetadata,
    VectorDBStats,
    serialize_for_storage,
    deserialize_from_storage,
    validate_metadata_compatibility
)

__all__ = [
    'TableChunk',
    'TableMetadata',
    'EnhancedTableMetadata',
    'VectorDBStats',
    'serialize_for_storage',
    'deserialize_from_storage',
    'validate_metadata_compatibility',
]
