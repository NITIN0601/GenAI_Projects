"""
Chunking utilities for embeddings.

Provides text and table chunking for embedding generation.
"""

from src.infrastructure.embeddings.chunking.table_chunker import TableChunker, get_table_chunker

__all__ = [
    'TableChunker',
    'get_table_chunker',
]
