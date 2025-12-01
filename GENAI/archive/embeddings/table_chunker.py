"""
Backward compatibility wrapper for old import paths.

This module provides backward compatibility for code using old import paths.
New code should use the new paths directly.

OLD: from embeddings.table_chunker import get_table_chunker
NEW: from data_processing.ingestion import get_table_chunker
"""

import warnings

# Import from new location
from data_processing.ingestion import get_table_chunker, TableChunker

# Warn about deprecated import
warnings.warn(
    "Importing from 'embeddings.table_chunker' is deprecated. "
    "Use 'from data_processing.ingestion import get_table_chunker' instead.",
    DeprecationWarning,
    stacklevel=2
)

__all__ = ['get_table_chunker', 'TableChunker']
