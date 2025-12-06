"""
Base classes for embedding providers.

Provides abstract base classes for implementing custom embedding providers.
"""

from abc import ABC, abstractmethod
from typing import List

# Import data models
from src.models import TableChunk, TableMetadata


class EmbeddingProvider(ABC):
    """Abstract base class for embedding providers."""
    
    @abstractmethod
    def generate_embedding(self, text: str) -> List[float]:
        """Generate embedding for a single text."""
        pass
    
    @abstractmethod
    def generate_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple texts."""
        pass
    
    @abstractmethod
    def get_embedding_dimension(self) -> int:
        """Get the dimension of embeddings produced by this provider."""
        pass
    
    @abstractmethod
    def get_provider_name(self) -> str:
        """Get the name of this provider."""
        pass


__all__ = [
    'EmbeddingProvider',
    'TableChunk',
    'TableMetadata'
]
