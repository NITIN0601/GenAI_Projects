"""
Embedding generation module.

Provides multi-provider embedding generation with support for:
- Local sentence-transformers (HuggingFace)
- Custom API providers
- Multi-level embeddings
- Table chunking

Example:
    >>> from src.infrastructure.embeddings import EmbeddingManager
    >>> manager = EmbeddingManager(provider="local")
    >>> embeddings = manager.embed_texts(["text1", "text2"])
"""

from src.infrastructure.embeddings.manager import EmbeddingManager, get_embedding_manager
from src.infrastructure.embeddings.multi_level import MultiLevelEmbeddingGenerator

__version__ = "2.0.0"

__all__ = [
    'EmbeddingManager',
    'get_embedding_manager',
    'MultiLevelEmbeddingGenerator'
]

