"""
VectorDB Manager - Unified vector database interface.

Provides thread-safe singleton access to vector database backends with support for:
- ChromaDB (persistent, default)
- FAISS (high-performance, in-memory)
- Redis Vector (distributed, production-scale)

Example:
    >>> from src.infrastructure.vectordb import get_vectordb_manager
    >>> 
    >>> # Get singleton instance
    >>> vectordb = get_vectordb_manager()
    >>> 
    >>> # Add chunks
    >>> vectordb.add_chunks(chunks)
    >>> 
    >>> # Search
    >>> results = vectordb.search("revenue", top_k=5)
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List, TYPE_CHECKING

from config.settings import settings
from src.core.singleton import ThreadSafeSingleton
from src.utils import get_logger

logger = get_logger(__name__)

if TYPE_CHECKING:
    from src.domain.tables import TableChunk


class VectorDBInterface(ABC):
    """
    Abstract interface for vector databases.
    
    All vector store implementations must implement these methods.
    Provides a consistent API regardless of the underlying backend.
    """
    
    @abstractmethod
    def add_chunks(
        self,
        chunks: List["TableChunk"],
        show_progress: bool = True
    ) -> int:
        """
        Add chunks to vector database.
        
        Args:
            chunks: List of TableChunk objects with embeddings
            show_progress: Show progress bar during ingestion
            
        Returns:
            Number of chunks added
        """
        ...
    
    @abstractmethod
    def search(
        self,
        query: str,
        top_k: int = 5,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Any]:
        """
        Search for similar chunks.
        
        Args:
            query: Search query text
            top_k: Number of results to return
            filters: Optional metadata filters
            
        Returns:
            List of SearchResult objects
        """
        ...
    
    @abstractmethod
    def get_by_metadata(
        self,
        filters: Dict[str, Any],
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Get chunks by metadata filters.
        
        Args:
            filters: Metadata filter criteria
            limit: Maximum results to return
            
        Returns:
            List of matching documents with metadata
        """
        ...
    
    @abstractmethod
    def delete_by_source(self, source_doc: str) -> int:
        """
        Delete all chunks from a source document.
        
        Args:
            source_doc: Source document identifier
            
        Returns:
            Number of chunks deleted
        """
        ...
    
    @abstractmethod
    def clear(self) -> None:
        """Clear all data from the vector store."""
        ...
    
    @abstractmethod
    def get_stats(self) -> Dict[str, Any]:
        """
        Get database statistics.
        
        Returns:
            Dict with count, size, and other metrics
        """
        ...
    
    @abstractmethod
    def get_provider_name(self) -> str:
        """Get provider name identifier."""
        ...


class VectorDBManager(metaclass=ThreadSafeSingleton):
    """
    Unified vector database manager.
    
    Thread-safe singleton manager for vector database backends.
    
    Supports:
    - ChromaDB (persistent, default)
    - FAISS (high-performance)
    - Redis Vector (distributed)
    
    Attributes:
        provider_name: Current provider type
        db: Underlying vector store instance
    """
    
    def __init__(
        self,
        provider: Optional[str] = None,
        embedding_manager: Any = None,
        **kwargs
    ):
        """
        Initialize vector database manager.
        
        Args:
            provider: "chromadb", "faiss", or "redis" (uses settings default if not provided)
            embedding_manager: Optional embedding manager (auto-creates if not provided)
            **kwargs: Provider-specific arguments
        """
        self.provider_name = (provider or settings.VECTORDB_PROVIDER).lower()
        self._embedding_manager = embedding_manager
        self._db: Optional[VectorDBInterface] = None
        
        # Initialize based on provider type
        self._initialize_provider(**kwargs)
    
    def _initialize_provider(self, **kwargs) -> None:
        """
        Initialize the appropriate vector store backend.
        
        Uses lazy imports to avoid loading unnecessary dependencies.
        """
        if self.provider_name == "chromadb":
            self._init_chromadb(**kwargs)
        elif self.provider_name == "faiss":
            self._init_faiss(**kwargs)
        elif self.provider_name == "redis":
            self._init_redis(**kwargs)
        else:
            raise ValueError(
                f"Unknown provider: {self.provider_name}. "
                f"Supported: 'chromadb', 'faiss', 'redis'"
            )
        
        logger.info(f"VectorDB Manager initialized: {self.provider_name}")
    
    def _get_embedding_manager(self):
        """Get or create embedding manager."""
        if self._embedding_manager is None:
            from src.infrastructure.embeddings.manager import get_embedding_manager
            self._embedding_manager = get_embedding_manager()
        return self._embedding_manager
    
    def _init_chromadb(self, **kwargs) -> None:
        """Initialize ChromaDB backend."""
        from src.infrastructure.vectordb.stores.chromadb_store import VectorStore
        
        self._db = VectorStore(
            persist_directory=kwargs.get('persist_directory'),
            collection_name=kwargs.get('collection_name')
        )
    
    def _init_faiss(self, **kwargs) -> None:
        """Initialize FAISS backend."""
        from src.infrastructure.vectordb.stores.faiss_store import FAISSVectorStore
        
        embedding_manager = self._get_embedding_manager()
        self._db = FAISSVectorStore(
            embedding_function=embedding_manager,
            dimension=kwargs.get('dimension'),
            persist_dir=kwargs.get('persist_dir'),
            index_type=kwargs.get('index_type', 'flat')
        )
    
    def _init_redis(self, **kwargs) -> None:
        """Initialize Redis Vector backend."""
        from src.infrastructure.vectordb.stores.redis_store import RedisVectorStore
        
        embedding_manager = self._get_embedding_manager()
        self._db = RedisVectorStore(
            embedding_function=embedding_manager,
            index_name=kwargs.get('index_name', 'financial_docs')
        )
    
    @property
    def db(self) -> VectorDBInterface:
        """Get the underlying vector store."""
        return self._db
    
    @property
    def name(self) -> str:
        """Provider name (implements BaseProvider protocol)."""
        return self.provider_name
    
    def is_available(self) -> bool:
        """Check if provider is available (implements BaseProvider protocol)."""
        try:
            stats = self._db.get_stats()
            return stats is not None
        except Exception:
            return False
    
    def health_check(self) -> Dict[str, Any]:
        """
        Perform health check (implements BaseProvider protocol).
        
        Returns:
            Dict with 'status' and optional details
        """
        try:
            stats = self.get_stats()
            return {
                "status": "ok",
                "provider": self.provider_name,
                "stats": stats,
            }
        except Exception as e:
            return {
                "status": "error",
                "provider": self.provider_name,
                "error": str(e),
            }
    
    def add_chunks(
        self,
        chunks: List["TableChunk"],
        show_progress: bool = True
    ) -> int:
        """
        Add chunks to vector database.
        
        Args:
            chunks: List of TableChunk objects
            show_progress: Show progress bar
            
        Returns:
            Number of chunks added
        """
        return self._db.add_chunks(chunks, show_progress)
    
    def search(
        self,
        query: str,
        top_k: int = 5,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Any]:
        """
        Search for similar chunks.
        
        Args:
            query: Search query
            top_k: Number of results
            filters: Optional metadata filters
            
        Returns:
            List of SearchResult objects
        """
        return self._db.search(query, top_k, filters)
    
    def get_by_metadata(
        self,
        filters: Dict[str, Any],
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Get chunks by metadata filters.
        
        Args:
            filters: Metadata filter criteria
            limit: Maximum results
            
        Returns:
            List of matching documents
        """
        return self._db.get_by_metadata(filters, limit)
    
    def delete_by_source(self, source_doc: str) -> int:
        """
        Delete all chunks from a source document.
        
        Args:
            source_doc: Source document identifier
            
        Returns:
            Number of deleted chunks
        """
        return self._db.delete_by_source(source_doc)
    
    def clear(self) -> None:
        """Clear all data from vector store."""
        return self._db.clear()
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get database statistics.
        
        Returns:
            Dict with database metrics
        """
        stats = self._db.get_stats()
        stats['provider'] = self.provider_name
        return stats
    
    def get_provider_info(self) -> Dict[str, Any]:
        """
        Get provider information.
        
        Returns:
            Dict with provider details and stats
        """
        return {
            "provider": self.provider_name,
            "available": self.is_available(),
            "stats": self.get_stats(),
        }


def get_vectordb_manager(
    provider: Optional[str] = None,
    **kwargs
) -> VectorDBManager:
    """
    Get or create global vector database manager.
    
    Thread-safe singleton accessor.
    
    Args:
        provider: "chromadb", "faiss", or "redis" (only used on first call)
        **kwargs: Provider-specific arguments (only used on first call)
        
    Returns:
        VectorDBManager singleton instance
    """
    return VectorDBManager(provider=provider, **kwargs)


def reset_vectordb_manager() -> None:
    """
    Reset the vector database manager singleton.
    
    Useful for testing or reconfiguration.
    """
    VectorDBManager._reset_instance()
