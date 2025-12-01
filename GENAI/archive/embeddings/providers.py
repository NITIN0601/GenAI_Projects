"""
Backward compatibility wrapper for old import paths.

This module provides backward compatibility for code using old import paths.
New code should use the new paths directly.

OLD: from embeddings.providers import get_embedding_manager
NEW: from models.embeddings import get_embedding_manager
"""

import warnings

# Import from new location
from models.embeddings import (
    get_embedding_manager,
    EmbeddingManager,
    EmbeddingProvider,
    OpenAIEmbeddingProvider,
    LocalEmbeddingProvider
)

# Warn about deprecated import
warnings.warn(
    "Importing from 'embeddings.providers' is deprecated. "
    "Use 'from models.embeddings import get_embedding_manager' instead.",
    DeprecationWarning,
    stacklevel=2
)

__all__ = [
    'get_embedding_manager',
    'EmbeddingManager',
    'EmbeddingProvider',
    'OpenAIEmbeddingProvider',
    'LocalEmbeddingProvider',
]
