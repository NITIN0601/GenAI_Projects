"""
Embedding generation module.

Provides multi-provider embedding generation with support for:
- OpenAI embeddings
- Local sentence-transformers
- Custom API providers
- Multi-level embeddings
- Table chunking

Example:
    >>> from src.embeddings.manager import EmbeddingManager
    >>> manager = EmbeddingManager(provider="local")
    >>> embeddings = manager.embed_texts(["text1", "text2"])
"""

__version__ = "2.0.0"

__all__ = []

