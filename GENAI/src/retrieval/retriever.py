"""
Retriever for semantic search and context building.

Provides thread-safe singleton access to document retrieval with support for:
- Semantic search via VectorDB
- Metadata filtering
- Context building for RAG
- Query filter parsing

Example:
    >>> from src.retrieval import get_retriever
    >>> 
    >>> retriever = get_retriever()
    >>> results = retriever.retrieve("revenue Q1 2024", top_k=5)
"""

import re
from typing import List, Dict, Any, Optional, TYPE_CHECKING

from src.core.singleton import ThreadSafeSingleton
from src.domain.tables import TableMetadata
from src.utils import get_logger

logger = get_logger(__name__)

if TYPE_CHECKING:
    from src.infrastructure.vectordb.manager import VectorDBManager
    from src.domain import SearchResult


class Retriever(metaclass=ThreadSafeSingleton):
    """
    Handles retrieval of relevant chunks from vector store.
    
    Thread-safe singleton manager for document retrieval.
    
    Supports semantic search and metadata filtering.
    
    Attributes:
        vector_store: VectorDBManager instance
    """
    
    def __init__(self, vector_store: Optional["VectorDBManager"] = None):
        """
        Initialize retriever.
        
        Args:
            vector_store: VectorDBManager instance (auto-created if None)
        """
        self._vector_store = vector_store
    
    @property
    def vector_store(self) -> "VectorDBManager":
        """Get vector store (lazy initialization)."""
        if self._vector_store is None:
            from src.infrastructure.vectordb.manager import get_vectordb_manager
            self._vector_store = get_vectordb_manager()
        return self._vector_store
    
    @property
    def name(self) -> str:
        """Provider name (implements BaseProvider protocol)."""
        return "retriever"
    
    def is_available(self) -> bool:
        """Check if retriever is available (implements BaseProvider protocol)."""
        try:
            return self.vector_store.is_available()
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
                "vector_store": self.vector_store.name if self._vector_store else "not initialized",
            }
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
            }
    
    def retrieve(
        self,
        query: str,
        top_k: int = 5,
        filters: Optional[Dict[str, Any]] = None,
        similarity_threshold: Optional[float] = None
    ) -> List["SearchResult"]:
        """
        Retrieve relevant chunks for a query.
        
        Args:
            query: Search query
            top_k: Number of results to retrieve
            filters: Metadata filters (e.g., {"year": 2025, "quarter": "Q2"})
            similarity_threshold: Minimum similarity score (0-1)
            
        Returns:
            List of SearchResult objects
        """
        from config.settings import settings
        
        if similarity_threshold is None:
            similarity_threshold = settings.SIMILARITY_THRESHOLD
        
        # Perform semantic search using VectorDBManager
        results = self.vector_store.search(
            query=query,
            top_k=top_k * 2,  # Get more results for filtering
            filters=filters
        )
        
        # Apply threshold if needed
        return results[:top_k]
    
    def build_context(
        self,
        retrieved_chunks: List["SearchResult"],
        max_context_length: int = 4000
    ) -> str:
        """
        Build context string from retrieved chunks.
        
        Args:
            retrieved_chunks: List of SearchResult objects
            max_context_length: Maximum context length in characters
            
        Returns:
            Formatted context string
        """
        context_parts = []
        current_length = 0
        
        for i, chunk in enumerate(retrieved_chunks, 1):
            metadata = chunk.metadata
            content = chunk.content
            
            # Format chunk with metadata
            chunk_text = f"\n--- Source {i} ---\n"
            chunk_text += f"Document: {metadata.source_doc}\n"
            chunk_text += f"Page: {metadata.page_no}\n"
            chunk_text += f"Table: {metadata.table_title}\n"
            
            if metadata.year:
                chunk_text += f"Year: {metadata.year}\n"
            if metadata.quarter:
                chunk_text += f"Quarter: {metadata.quarter}\n"
            
            chunk_text += f"\nContent:\n{content}\n"
            
            # Check if adding this chunk would exceed max length
            if current_length + len(chunk_text) > max_context_length:
                break
            
            context_parts.append(chunk_text)
            current_length += len(chunk_text)
        
        return "\n".join(context_parts)
    
    def extract_sources(
        self,
        retrieved_chunks: List["SearchResult"]
    ) -> List[TableMetadata]:
        """
        Extract source metadata from retrieved chunks.
        
        Args:
            retrieved_chunks: List of SearchResult objects
            
        Returns:
            List of TableMetadata objects
        """
        sources = []
        seen = set()
        
        for chunk in retrieved_chunks:
            metadata = chunk.metadata
            
            key = (
                metadata.source_doc,
                metadata.page_no,
                metadata.table_title
            )
            
            if key not in seen:
                seen.add(key)
                sources.append(metadata)
        
        return sources
    
    def parse_query_filters(self, query: str) -> Dict[str, Any]:
        """
        Parse query to extract metadata filters.
        
        Args:
            query: User query
            
        Returns:
            Dictionary of filters
        """
        filters = {}
        query_lower = query.lower()
        
        # Extract year
        year_match = re.search(r'20\d{2}', query)
        if year_match:
            filters['year'] = int(year_match.group(0))
        
        # Extract quarter
        quarter_patterns = [
            (r'\bq1\b', 'Q1'),
            (r'\bq2\b', 'Q2'),
            (r'\bq3\b', 'Q3'),
            (r'\bq4\b', 'Q4'),
            (r'first quarter', 'Q1'),
            (r'second quarter', 'Q2'),
            (r'third quarter', 'Q3'),
            (r'fourth quarter', 'Q4'),
        ]
        
        for pattern, quarter in quarter_patterns:
            if re.search(pattern, query_lower):
                filters['quarter'] = quarter
                break
        
        # Extract table type
        table_type_keywords = {
            'balance sheet': 'Balance Sheet',
            'income statement': 'Income Statement',
            'cash flow': 'Cash Flow Statement',
        }
        
        for keyword, table_type in table_type_keywords.items():
            if keyword in query_lower:
                filters['table_type'] = table_type
                break
        
        return filters


def get_retriever(
    vector_store: Optional["VectorDBManager"] = None
) -> Retriever:
    """
    Get or create global retriever instance.
    
    Thread-safe singleton accessor.
    
    Args:
        vector_store: VectorDBManager instance (only used on first call)
        
    Returns:
        Retriever singleton instance
    """
    return Retriever(vector_store=vector_store)


def reset_retriever() -> None:
    """
    Reset the retriever singleton.
    
    Useful for testing or reconfiguration.
    """
    Retriever._reset_instance()
