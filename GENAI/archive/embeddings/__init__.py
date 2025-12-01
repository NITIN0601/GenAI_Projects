"""
Embeddings module with multi-provider support.

Supports:
- OpenAI (text-embedding-3-small, text-embedding-ada-002)
- Local (sentence-transformers)

Recommended usage:
    from embeddings.providers import get_embedding_manager
    em = get_embedding_manager(provider="openai", api_key="sk-...")
"""

# New provider system (RECOMMENDED)
from embeddings.providers import (
    EmbeddingProvider,
    OpenAIEmbeddingProvider,
    LocalEmbeddingProvider,
    EmbeddingManager,
    get_embedding_manager
)

# VectorDB manager
from embeddings.vectordb_manager import (
    VectorDBManager,
    get_vectordb_manager
)

# Backward compatibility (deprecated)
from embeddings.embedding_manager import (
    EmbeddingManager as LegacyEmbeddingManager,
    get_embedding_manager as get_legacy_embedding_manager
)

from embeddings.vector_store import (
    VectorStore,
    get_vector_store
)

from embeddings.faiss_store import (
    FAISSVectorStore,
    get_faiss_store
)

from data_processing.ingestion import (
    TableChunker,
    get_table_chunker
)

__all__ = [
    # Provider system (recommended)
    'EmbeddingProvider',
    'OpenAIEmbeddingProvider',
    'LocalEmbeddingProvider',
    'EmbeddingManager',
    'get_embedding_manager',
    
    # VectorDB manager
    'VectorDBManager',
    'get_vectordb_manager',
    
    # Backward compatibility
    'LegacyEmbeddingManager',
    'get_legacy_embedding_manager',
    'VectorStore',
    'get_vector_store',
    'FAISSVectorStore',
    'get_faiss_store',
    'TableChunker',
    'get_table_chunker',
]
