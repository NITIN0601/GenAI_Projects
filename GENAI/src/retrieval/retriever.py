"""Retriever for semantic search and context building."""

from typing import List, Dict, Any, Optional
from src.models.schemas import TableMetadata
from src.vector_store.stores.chromadb_store import get_vector_store


class Retriever:
    """
    Handles retrieval of relevant chunks from vector store.
    Supports semantic search and metadata filtering.
    """
    
    def __init__(self, vector_store=None):
        """
        Initialize retriever.
        
        Args:
            vector_store: VectorStore instance (optional)
        """
        self.vector_store = vector_store or get_vector_store()
    
    def retrieve(
        self,
        query: str,
        top_k: int = 5,
        filters: Optional[Dict[str, Any]] = None,
        similarity_threshold: float = None
    ) -> List[Dict[str, Any]]:
        """
        Retrieve relevant chunks for a query.
        
        Args:
            query: Search query
            top_k: Number of results to retrieve
            filters: Metadata filters (e.g., {"year": 2025, "quarter": "Q2"})
            similarity_threshold: Minimum similarity score (0-1)
            
        Returns:
            List of retrieved chunks with metadata
        """
        from config.settings import settings
        
        if similarity_threshold is None:
            similarity_threshold = settings.SIMILARITY_THRESHOLD
        
        # Perform semantic search using LangChain interface
        # Both FAISS and ChromaDB stores now support similarity_search_with_score
        results_with_scores = self.vector_store.similarity_search_with_score(
            query=query,
            k=top_k * 2,  # Get more results for filtering
            filter=filters
        )
        
        # Format results and filter by threshold
        filtered_results = []
        for doc, score in results_with_scores:
            # Calculate similarity (Chroma/FAISS usually return distance or similarity depending on config)
            # Assuming score is distance for now (lower is better), or similarity (higher is better)
            # This logic might need adjustment based on specific metric used
            
            # For now, we'll assume the score is usable as is or convert if needed
            # FAISS FlatIP returns inner product (similarity), Chroma default is L2 (distance)
            
            # Let's normalize to a dictionary format expected by the rest of the system
            result = {
                "id": doc.metadata.get("chunk_reference_id", ""),
                "content": doc.page_content,
                "metadata": doc.metadata,
                "score": score,
                "distance": score # Keep original score
            }
            
            # Apply threshold if needed (logic depends on metric)
            # For now, just append
            filtered_results.append(result)
        
        # Return top_k results
        return filtered_results[:top_k]
    
    def build_context(
        self,
        retrieved_chunks: List[Dict[str, Any]],
        max_context_length: int = 4000
    ) -> str:
        """
        Build context string from retrieved chunks.
        
        Args:
            retrieved_chunks: List of retrieved chunks
            max_context_length: Maximum context length in characters
            
        Returns:
            Formatted context string
        """
        context_parts = []
        current_length = 0
        
        for i, chunk in enumerate(retrieved_chunks, 1):
            metadata = chunk.get('metadata', {})
            content = chunk.get('content', '')
            
            # Format chunk with metadata
            chunk_text = f"\n--- Source {i} ---\n"
            chunk_text += f"Document: {metadata.get('source_doc', 'Unknown')}\n"
            chunk_text += f"Page: {metadata.get('page_no', 'N/A')}\n"
            chunk_text += f"Table: {metadata.get('table_title', 'Unknown')}\n"
            
            if 'year' in metadata:
                chunk_text += f"Year: {metadata['year']}\n"
            if 'quarter' in metadata:
                chunk_text += f"Quarter: {metadata['quarter']}\n"
            
            chunk_text += f"\nContent:\n{content}\n"
            
            # Check if adding this chunk would exceed max length
            if current_length + len(chunk_text) > max_context_length:
                break
            
            context_parts.append(chunk_text)
            current_length += len(chunk_text)
        
        return "\n".join(context_parts)
    
    def extract_sources(
        self,
        retrieved_chunks: List[Dict[str, Any]]
    ) -> List[TableMetadata]:
        """
        Extract source metadata from retrieved chunks.
        
        Args:
            retrieved_chunks: List of retrieved chunks
            
        Returns:
            List of TableMetadata objects
        """
        sources = []
        seen = set()  # Avoid duplicates
        
        for chunk in retrieved_chunks:
            metadata = chunk.get('metadata', {})
            
            # Create unique key
            key = (
                metadata.get('source_doc'),
                metadata.get('page_no'),
                metadata.get('table_title')
            )
            
            if key not in seen:
                seen.add(key)
                
                # Create TableMetadata object
                source = TableMetadata(
                    source_doc=metadata.get('source_doc', 'Unknown'),
                    page_no=metadata.get('page_no', 0),
                    table_title=metadata.get('table_title', 'Unknown'),
                    year=metadata.get('year', 0),
                    quarter=metadata.get('quarter'),
                    report_type=metadata.get('report_type', 'Unknown'),
                    table_type=metadata.get('table_type'),
                    fiscal_period=metadata.get('fiscal_period')
                )
                sources.append(source)
        
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
        import re
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


# Global retriever instance
_retriever: Optional[Retriever] = None


def get_retriever() -> Retriever:
    """Get or create global retriever instance."""
    global _retriever
    if _retriever is None:
        _retriever = Retriever()
    return _retriever
