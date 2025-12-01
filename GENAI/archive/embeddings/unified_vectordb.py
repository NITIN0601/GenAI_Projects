"""
Backward compatibility wrapper for old import paths.

This module provides backward compatibility for code using old import paths.
New code should use the new paths directly.

OLD: from embeddings.unified_vectordb import get_unified_vectordb
NEW: from vectordb import get_vectordb
"""

import warnings

# Import from new location
from vectordb import (
    get_vectordb,
    UnifiedVectorDBInterface,
    ChromaDBBackend,
    FAISSBackend,
    TableChunk,
    TableMetadata,
    EnhancedTableMetadata,
    VectorDBStats
)

# Provide old names for backward compatibility
get_unified_vectordb = get_vectordb

# Warn about deprecated import
warnings.warn(
    "Importing from 'embeddings.unified_vectordb' is deprecated. "
    "Use 'from vectordb import get_vectordb' instead.",
    DeprecationWarning,
    stacklevel=2
)

__all__ = [
    'get_unified_vectordb',
    'get_vectordb',
    'UnifiedVectorDBInterface',
    'ChromaDBBackend',
    'FAISSBackend',
    'TableChunk',
    'TableMetadata',
    'EnhancedTableMetadata',
    'VectorDBStats',
]
