"""
Backward compatibility wrapper for old import paths.

This module provides backward compatibility for code using old import paths.
New code should use the new paths directly.

OLD: from models.vectordb_schemas import TableChunk, EnhancedTableMetadata
NEW: from vectordb.schemas import TableChunk, EnhancedTableMetadata
"""

import warnings

# Import from new location
from vectordb.schemas import (
    TableChunk,
    TableMetadata,
    EnhancedTableMetadata,
    VectorDBStats,
    serialize_for_storage,
    deserialize_from_storage,
    validate_metadata_compatibility
)

# Warn about deprecated import
warnings.warn(
    "Importing from 'models.vectordb_schemas' is deprecated. "
    "Use 'from vectordb.schemas import ...' instead.",
    DeprecationWarning,
    stacklevel=2
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
