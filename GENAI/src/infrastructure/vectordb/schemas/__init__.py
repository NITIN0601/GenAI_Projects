"""
VectorDB schemas module.

Uses the comprehensive TableMetadata from extraction as the source of truth.
Provides provider-specific conversion utilities for FAISS, ChromaDB, and Redis.

Key principle: Store ALL extracted metadata, index only the most useful fields.
"""

from src.infrastructure.vectordb.schemas.vectordb_schemas import (
    VectorDBProvider,
    VectorDBIndexConfig,
    VectorDBSchemaConverter,
    VectorDBStats,
    DEFAULT_INDEX_CONFIG,
    get_redis_schema_fields,
    get_redis_vector_field,
)

# Re-export the core schemas from models
from src.domain.tables import TableMetadata, TableChunk

__all__ = [
    # Core schemas (from extraction)
    'TableMetadata',
    'TableChunk',
    # VectorDB utilities
    'VectorDBProvider',
    'VectorDBIndexConfig',
    'VectorDBSchemaConverter',
    'VectorDBStats',
    'DEFAULT_INDEX_CONFIG',
    'get_redis_schema_fields',
    'get_redis_vector_field',
]
