"""
Vector store using LangChain Chroma wrapper.

Unified vector store implementation compatible with LangChain ecosystem.
"""

from typing import List, Dict, Any, Optional
import logging
import uuid

from langchain_chroma import Chroma
from langchain_core.vectorstores import VectorStore as BaseVectorStore
from langchain_core.documents import Document

from config.settings import settings
from src.models.schemas import TableChunk
from src.utils import get_logger
from src.infrastructure.embeddings.manager import get_embedding_manager

logger = get_logger(__name__)


class VectorStore:
    """
    Unified Vector Store wrapping LangChain Chroma.
    """
    
    def __init__(
        self,
        persist_directory: Optional[str] = None,
        collection_name: Optional[str] = None,
        embedding_manager = None
    ):
        """
        Initialize Vector Store.
        """
        self.persist_directory = persist_directory or settings.CHROMA_PERSIST_DIR
        self.collection_name = collection_name or settings.CHROMA_COLLECTION_NAME
        
        # Dependency Injection
        self.embedding_manager = embedding_manager or get_embedding_manager()
        
        logger.info(f"Initializing LangChain Chroma: {self.collection_name}")
        
        # Initialize LangChain Chroma
        self.vector_db = Chroma(
            collection_name=self.collection_name,
            embedding_function=self.embedding_manager,
            persist_directory=self.persist_directory
        )
        
    def add_chunks(self, chunks: List[TableChunk], show_progress: bool = True):
        """
        Add chunks to vector store.
        
        Args:
            chunks: List of TableChunk objects
        """
        if not chunks:
            return
            
        # Convert to LangChain Documents
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
            
        # Add to Chroma
        try:
            self.vector_db.add_documents(documents=documents, ids=ids)
            logger.info(f"Added {len(documents)} chunks to vector store")
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
            filters: Metadata filters
            
        Returns:
            List of SearchResult objects
        """
        from src.models.schemas import SearchResult, TableMetadata
        
        try:
            if query_text:
                # Use LangChain's similarity_search_with_score
                docs_and_scores = self.vector_db.similarity_search_with_score(
                    query_text,
                    k=top_k,
                    filter=filter
                )
            elif query_embedding:
                # Search by embedding
                docs_and_scores = self.vector_db.similarity_search_by_vector_with_score(
                    query_embedding,
                    k=top_k,
                    filter=filter
                )
            else:
                return []
                
            # Convert to standard format
            results = []
            for doc, score in docs_and_scores:
                # Create TableMetadata from doc.metadata
                # We need to handle potential missing fields gracefully
                try:
                    metadata = TableMetadata(**doc.metadata)
                except Exception:
                    # Fallback for incomplete metadata
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

    def similarity_search_with_score(self, query: str, k: int = 4, **kwargs) -> List[tuple[Document, float]]:
        """Run similarity search with score."""
        return self.vector_db.similarity_search_with_score(query, k=k, **kwargs)

    def get_langchain_store(self):
        """Return underlying LangChain vector store."""
        return self.vector_db


# Global instance
_vector_store: Optional[VectorStore] = None

def get_vector_store() -> VectorStore:
    """Get global vector store."""
    global _vector_store
    if _vector_store is None:
        _vector_store = VectorStore()
    return _vector_store
