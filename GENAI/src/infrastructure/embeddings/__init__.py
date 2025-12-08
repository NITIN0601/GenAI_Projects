"""
Embedding Generation Module.

Provides multi-provider embedding generation with support for:
- Local sentence-transformers (HuggingFace, default)
- OpenAI embedding models
- Custom API providers
- Multi-level embeddings (table, row, cell)
- Table chunking

Thread-Safe Singleton:
    The EmbeddingManager uses ThreadSafeSingleton pattern for consistent
    instance management across the application.

Example:
    >>> from src.infrastructure.embeddings import get_embedding_manager
    >>> 
    >>> # Get singleton instance
    >>> embeddings = get_embedding_manager()
    >>> vector = embeddings.embed_query("What is AI?")
    >>> 
    >>> # Embed multiple documents
    >>> vectors = embeddings.embed_documents(["doc1", "doc2"])
"""

from src.infrastructure.embeddings.manager import (
    EmbeddingManager,
    get_embedding_manager,
    reset_embedding_manager,
)
from src.infrastructure.embeddings.langchain_wrapper import CustomLangChainEmbeddings
from src.infrastructure.embeddings.multi_level import MultiLevelEmbeddingGenerator

__version__ = "2.1.0"

__all__ = [
    # Manager
    'EmbeddingManager',
    'get_embedding_manager',
    'reset_embedding_manager',
    # Wrappers
    'CustomLangChainEmbeddings',
    # Multi-level
    'MultiLevelEmbeddingGenerator',
]
