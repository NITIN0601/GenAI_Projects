"""
VectorDB module - Unified vector database interface.

Provides consistent API across multiple VectorDB backends:
- ChromaDB (persistent, default)
- FAISS (high-performance, in-memory)
- Redis Vector (distributed, scalable)

Usage:
    from vectordb import get_vectordb
    
    # Auto-loads from settings.VECTORDB_PROVIDER
    db = get_vectordb()
    
    # Or specify provider
    db = get_vectordb(provider="chromadb")
"""

from vectordb.interface import (
    UnifiedVectorDBInterface,
    ChromaDBBackend,
    FAISSBackend,
    get_unified_vectordb as get_vectordb
)

from vectordb.schemas import (
    TableChunk,
    TableMetadata,
    EnhancedTableMetadata,
    VectorDBStats
)

__all__ = [
    # Interface
    'UnifiedVectorDBInterface',
    'get_vectordb',
    
    # Backends
    'ChromaDBBackend',
    'FAISSBackend',
    
    # Schemas
    'TableChunk',
    'TableMetadata',
    'EnhancedTableMetadata',
    'VectorDBStats',
]
