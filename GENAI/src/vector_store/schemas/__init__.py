"""
Vector store schemas.

Data models for vector store documents and metadata.

Note: Vector store schemas are now in src/models/schemas.
Import from there for TableMetadata, TableChunk, etc.
"""

# Re-export from centralized models for convenience
from src.models.schemas import (
    TableMetadata,
    TableChunk,
    SearchResult,
)

__all__ = [
    'TableMetadata',
    'TableChunk', 
    'SearchResult',
]
