"""
Unified VectorDB interface supporting multiple backends.

Supports:
- ChromaDB (default, persistent)
- FAISS (high-performance, in-memory)
- Redis Vector (distributed, optional)
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List
import os

from src.utils import get_logger
from src.embeddings.manager import get_embedding_manager

logger = get_logger(__name__)
from src.models.schemas import TableChunk


class VectorDBInterface(ABC):
    """Abstract interface for vector databases."""
    
    @abstractmethod
    def add_chunks(
        self,
        chunks: List[TableChunk],
        show_progress: bool = True
    ):
        """Add chunks to vector database."""
        pass
    
    @abstractmethod
    def search(
        self,
        query: str,
        top_k: int = 5,
        filters: Optional[Dict[str, Any]] = None
    ) -> List["SearchResult"]:
        """Search for similar chunks."""
        pass
    
    @abstractmethod
    def get_by_metadata(
        self,
        filters: Dict[str, Any],
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get chunks by metadata filters."""
        pass
    
    @abstractmethod
    def delete_by_source(self, source_doc: str):
        """Delete all chunks from a source document."""
        pass
    
    @abstractmethod
    def clear(self):
        """Clear all data."""
        pass
    
    @abstractmethod
    def get_stats(self) -> Dict[str, Any]:
        """Get database statistics."""
        pass
    
    @abstractmethod
    def get_provider_name(self) -> str:
        """Get provider name."""
        pass


class VectorDBManager:
    """
    Unified vector database manager.
    
    Supports:
    - ChromaDB (default)
    - FAISS (high-performance)
    - Redis Vector (distributed)
    """
    
    def __init__(
        self,
        provider: str = "chromadb",
        **kwargs
    ):
        """
        Initialize vector database manager.
        
        Args:
            provider: "chromadb", "faiss", or "redis"
            **kwargs: Provider-specific arguments
        """
        self.provider_name = provider.lower()
        
        if self.provider_name == "chromadb":
            from src.vector_store.stores.chromadb_store import VectorStore
            self.db = VectorStore(
                persist_directory=kwargs.get('persist_directory'),
                collection_name=kwargs.get('collection_name')
            )
        elif self.provider_name == "faiss":
            from src.vector_store.stores.faiss_store import FAISSVectorStore
            embedding_manager = get_embedding_manager()
            self.db = FAISSVectorStore(
                embedding_function=embedding_manager.langchain_embeddings,
                dimension=kwargs.get('dimension'),
                persist_dir=kwargs.get('persist_dir'),
                index_type=kwargs.get('index_type', 'flat')
            )
        elif self.provider_name == "redis":
            from src.vector_store.stores.redis_store import RedisVectorStore
            self.db = RedisVectorStore(
                embedding_function=get_embedding_manager(),
                index_name=kwargs.get('index_name', 'financial_docs')
            )
        else:
            raise ValueError(
                f"Unknown provider: {provider}. "
                f"Supported: 'chromadb', 'faiss', 'redis'"
            )
        
        logger.info(f"VectorDB Manager: {self.provider_name}")
    
    def add_chunks(
        self,
        chunks: List[TableChunk],
        show_progress: bool = True
    ):
        """Add chunks to vector database."""
        return self.db.add_chunks(chunks, show_progress)
    
    def search(
        self,
        query: str,
        top_k: int = 5,
        filters: Optional[Dict[str, Any]] = None
    ) -> List["SearchResult"]:
        """Search for similar chunks."""
        return self.db.search(query, top_k, filters)
    
    def get_by_metadata(
        self,
        filters: Dict[str, Any],
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get chunks by metadata filters."""
        return self.db.get_by_metadata(filters, limit)
    
    def delete_by_source(self, source_doc: str):
        """Delete all chunks from a source document."""
        return self.db.delete_by_source(source_doc)
    
    def clear(self):
        """Clear all data."""
        return self.db.clear()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get database statistics."""
        stats = self.db.get_stats()
        stats['provider'] = self.provider_name
        return stats
    
    def get_provider_info(self) -> dict:
        """Get provider information."""
        return {
            "provider": self.provider_name,
            "stats": self.get_stats()
        }


# Global instance
_vectordb_manager: Optional[VectorDBManager] = None


def get_vectordb_manager(
    provider: Optional[str] = None,
    **kwargs
) -> VectorDBManager:
    """
    Get or create global vector database manager.
    
    Args:
        provider: "chromadb", "faiss", or "redis" (default: from config)
        **kwargs: Provider-specific arguments
    """
    global _vectordb_manager
    
    # Use config if not specified
    if provider is None:
        from config.settings import settings
        provider = getattr(settings, 'VECTORDB_PROVIDER', 'chromadb')
    
    if _vectordb_manager is None:
        _vectordb_manager = VectorDBManager(provider=provider, **kwargs)
    
    return _vectordb_manager
