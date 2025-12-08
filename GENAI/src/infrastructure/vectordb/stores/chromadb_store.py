"""
ChromaDB Vector Store implementation.

Provides thread-safe singleton access to ChromaDB with support for:
- LangChain Chroma integration
- Document chunking and storage
- Similarity search with scores
- Metadata filtering

Example:
    >>> from src.infrastructure.vectordb.stores.chromadb_store import get_vector_store
    >>> 
    >>> store = get_vector_store()
    >>> store.add_chunks(chunks)
    >>> results = store.search("revenue Q1", top_k=5)
"""

from typing import List, Dict, Any, Optional
import uuid

from langchain_chroma import Chroma
from langchain_core.documents import Document

from config.settings import settings
from src.core.singleton import ThreadSafeSingleton
from src.domain.tables import TableChunk
from src.utils import get_logger

logger = get_logger(__name__)


class VectorStore(metaclass=ThreadSafeSingleton):
    """
    Unified Vector Store wrapping LangChain Chroma.
    
    Thread-safe singleton manager for ChromaDB.
    
    Attributes:
        persist_directory: Directory for persistent storage
        collection_name: ChromaDB collection name
        embedding_manager: Embedding manager instance
    """
    
    def __init__(
        self,
        persist_directory: Optional[str] = None,
        collection_name: Optional[str] = None,
        embedding_manager=None
    ):
        """
        Initialize Vector Store.
        
        Args:
            persist_directory: Path for persistent storage (uses settings default if None)
            collection_name: ChromaDB collection name (uses settings default if None)
            embedding_manager: Embedding manager (auto-created if None)
        """
        self.persist_directory = persist_directory or settings.CHROMA_PERSIST_DIR
        self.collection_name = collection_name or settings.CHROMA_COLLECTION_NAME
        self._embedding_manager = embedding_manager
        
        logger.info(f"Initializing LangChain Chroma: {self.collection_name}")
        
        # Initialize LangChain Chroma
        self.vector_db = Chroma(
            collection_name=self.collection_name,
            embedding_function=self.embedding_manager,
            persist_directory=self.persist_directory
        )
    
    @property
    def embedding_manager(self):
        """Get embedding manager (lazy initialization)."""
        if self._embedding_manager is None:
            from src.infrastructure.embeddings.manager import get_embedding_manager
            self._embedding_manager = get_embedding_manager()
        return self._embedding_manager
    
    @property
    def name(self) -> str:
        """Provider name (implements BaseProvider protocol)."""
        return "chromadb"
    
    def is_available(self) -> bool:
        """Check if store is available (implements BaseProvider protocol)."""
        try:
            return self.vector_db is not None
        except Exception:
            return False
    
    def health_check(self) -> Dict[str, Any]:
        """
        Perform health check (implements BaseProvider protocol).
        
        Returns:
            Dict with 'status' and optional details
        """
        try:
            available = self.is_available()
            return {
                "status": "ok" if available else "error",
                "collection_name": self.collection_name,
                "persist_directory": self.persist_directory,
            }
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
            }
    
    def add_chunks(self, chunks: List[TableChunk], show_progress: bool = True) -> int:
        """
        Add chunks to vector store.
        
        Args:
            chunks: List of TableChunk objects
            show_progress: Whether to show progress bar
            
        Returns:
            Number of chunks added
        """
        if not chunks:
            return 0
            
        documents = []
        ids = []
        
        for chunk in chunks:
            # Convert metadata values to strings/ints/floats (Chroma restriction)
            clean_metadata = {}
            for k, v in chunk.metadata.dict().items():
                if v is not None:
                    if isinstance(v, (str, int, float, bool)):
                        clean_metadata[k] = v
                    else:
                        clean_metadata[k] = str(v)
            
            doc = Document(
                page_content=chunk.content,
                metadata=clean_metadata
            )
            documents.append(doc)
            ids.append(chunk.chunk_id)
            
        try:
            self.vector_db.add_documents(documents=documents, ids=ids)
            logger.info(f"Added {len(documents)} chunks to vector store")
            return len(documents)
        except Exception as e:
            logger.error(f"Failed to add chunks: {e}")
            raise

    def search(
        self,
        query_text: Optional[str] = None,
        query_embedding: Optional[List[float]] = None,
        top_k: int = 5,
        filter: Optional[Dict[str, Any]] = None
    ) -> List["SearchResult"]:
        """
        Search vector store.
        
        Args:
            query_text: Search query
            query_embedding: Optional pre-computed embedding
            top_k: Number of results
            filter: Metadata filters
            
        Returns:
            List of SearchResult objects
        """
        from src.domain import SearchResult, TableMetadata
        
        try:
            if query_text:
                docs_and_scores = self.vector_db.similarity_search_with_score(
                    query_text,
                    k=top_k,
                    filter=filter
                )
            elif query_embedding:
                docs_and_scores = self.vector_db.similarity_search_by_vector_with_score(
                    query_embedding,
                    k=top_k,
                    filter=filter
                )
            else:
                return []
                
            results = []
            for doc, score in docs_and_scores:
                try:
                    metadata = TableMetadata(**doc.metadata)
                except Exception:
                    metadata = TableMetadata(
                        source_doc=doc.metadata.get("source_doc", "unknown"),
                        page_no=int(doc.metadata.get("page_no", 0)),
                        table_title=doc.metadata.get("table_title", "unknown"),
                        year=int(doc.metadata.get("year", 0)),
                        report_type=doc.metadata.get("report_type", "unknown")
                    )

                results.append(SearchResult(
                    chunk_id=doc.metadata.get("chunk_reference_id", str(uuid.uuid4())),
                    content=doc.page_content,
                    metadata=metadata,
                    score=score,
                    distance=score
                ))
                
            return results
            
        except Exception as e:
            logger.error(f"Search failed: {e}")
            return []
            
    def as_retriever(self, **kwargs):
        """Return LangChain retriever."""
        return self.vector_db.as_retriever(**kwargs)

    def similarity_search(self, query: str, k: int = 4, **kwargs) -> List[Document]:
        """Run similarity search."""
        return self.vector_db.similarity_search(query, k=k, **kwargs)

    def similarity_search_with_score(self, query: str, k: int = 4, **kwargs) -> List[tuple]:
        """Run similarity search with score."""
        return self.vector_db.similarity_search_with_score(query, k=k, **kwargs)

    def get_langchain_store(self):
        """Return underlying LangChain vector store."""
        return self.vector_db
    
    def get_stats(self) -> Dict[str, Any]:
        """Get store statistics."""
        try:
            collection = self.vector_db._collection
            count = collection.count() if collection else 0
            return {
                "count": count,
                "collection_name": self.collection_name,
                "persist_directory": self.persist_directory,
            }
        except Exception as e:
            return {"error": str(e)}
    
    def get_provider_name(self) -> str:
        """Get provider name identifier."""
        return "chromadb"


def get_vector_store(
    persist_directory: Optional[str] = None,
    collection_name: Optional[str] = None,
    **kwargs
) -> VectorStore:
    """
    Get or create global vector store instance.
    
    Thread-safe singleton accessor.
    
    Args:
        persist_directory: Path for persistent storage (only used on first call)
        collection_name: ChromaDB collection name (only used on first call)
        
    Returns:
        VectorStore singleton instance
    """
    return VectorStore(
        persist_directory=persist_directory,
        collection_name=collection_name,
        **kwargs
    )


def reset_vector_store() -> None:
    """
    Reset the vector store singleton.
    
    Useful for testing or reconfiguration.
    """
    VectorStore._reset_instance()
