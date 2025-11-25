"""Vector store using ChromaDB (FREE & LOCAL)."""

from typing import List, Dict, Any, Optional
import chromadb
from chromadb.config import Settings as ChromaSettings
from chromadb.utils import embedding_functions
import uuid

from config.settings import settings
from models.schemas import TableChunk, TableMetadata
from embeddings.embedding_manager import get_embedding_manager


class VectorStore:
    """
    Vector database using ChromaDB (FREE & OPEN SOURCE).
    No cloud services or API keys required!
    """
    
    def __init__(self, persist_directory: Optional[str] = None, collection_name: Optional[str] = None):
        """
        Initialize ChromaDB vector store.
        
        Args:
            persist_directory: Directory to persist the database
            collection_name: Name of the collection
        """
        self.persist_directory = persist_directory or settings.CHROMA_PERSIST_DIR
        self.collection_name = collection_name or settings.CHROMA_COLLECTION_NAME
        
        # Initialize ChromaDB client
        self.client = chromadb.PersistentClient(
            path=self.persist_directory,
            settings=ChromaSettings(
                anonymized_telemetry=False,
                allow_reset=True
            )
        )
        
        # Get or create collection
        self.collection = self.client.get_or_create_collection(
            name=self.collection_name,
            metadata={"description": "Financial tables from SEC filings"}
        )
        
        self.embedding_manager = get_embedding_manager()
        
        print(f"Vector store initialized: {self.collection_name}")
        print(f"Persist directory: {self.persist_directory}")
    
    def add_chunks(self, chunks: List[TableChunk], show_progress: bool = True):
        """
        Add chunks to the vector store.
        
        Args:
            chunks: List of TableChunk objects
            show_progress: Show progress bar
        """
        if not chunks:
            return
        
        # Prepare data for ChromaDB
        ids = []
        documents = []
        embeddings = []
        metadatas = []
        
        for chunk in chunks:
            ids.append(chunk.chunk_id)
            documents.append(chunk.content)
            
            # Generate embedding if not already present
            if chunk.embedding is None:
                embedding = self.embedding_manager.generate_embedding(chunk.content)
            else:
                embedding = chunk.embedding
            
            embeddings.append(embedding)
            
            # Convert metadata to dict
            metadata_dict = {
                "source_doc": chunk.metadata.source_doc,
                "page_no": chunk.metadata.page_no,
                "table_title": chunk.metadata.table_title,
                "year": chunk.metadata.year,
                "report_type": chunk.metadata.report_type,
            }
            
            # Add optional fields
            if chunk.metadata.quarter:
                metadata_dict["quarter"] = chunk.metadata.quarter
            if chunk.metadata.table_type:
                metadata_dict["table_type"] = chunk.metadata.table_type
            if chunk.metadata.fiscal_period:
                metadata_dict["fiscal_period"] = chunk.metadata.fiscal_period
            
            metadatas.append(metadata_dict)
        
        # Add to collection
        self.collection.add(
            ids=ids,
            documents=documents,
            embeddings=embeddings,
            metadatas=metadatas
        )
        
        print(f"Added {len(chunks)} chunks to vector store")
    
    def search(
        self,
        query: str,
        top_k: int = 5,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Search for similar chunks using semantic search.
        
        Args:
            query: Search query
            top_k: Number of results to return
            filters: Metadata filters (e.g., {"year": 2025, "quarter": "Q2"})
            
        Returns:
            List of search results with content and metadata
        """
        # Generate query embedding
        query_embedding = self.embedding_manager.generate_embedding(query)
        
        # Build where clause for filters
        where_clause = None
        if filters:
            where_clause = {}
            for key, value in filters.items():
                if value is not None:
                    where_clause[key] = value
        
        # Search
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            where=where_clause if where_clause else None
        )
        
        # Format results
        formatted_results = []
        if results['ids'] and results['ids'][0]:
            for i in range(len(results['ids'][0])):
                result = {
                    'id': results['ids'][0][i],
                    'content': results['documents'][0][i],
                    'metadata': results['metadatas'][0][i],
                    'distance': results['distances'][0][i] if 'distances' in results else None
                }
                formatted_results.append(result)
        
        return formatted_results
    
    def get_by_metadata(
        self,
        filters: Dict[str, Any],
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Get chunks by metadata filters.
        
        Args:
            filters: Metadata filters
            limit: Maximum number of results
            
        Returns:
            List of matching chunks
        """
        where_clause = {}
        for key, value in filters.items():
            if value is not None:
                where_clause[key] = value
        
        results = self.collection.get(
            where=where_clause,
            limit=limit
        )
        
        formatted_results = []
        if results['ids']:
            for i in range(len(results['ids'])):
                result = {
                    'id': results['ids'][i],
                    'content': results['documents'][i],
                    'metadata': results['metadatas'][i]
                }
                formatted_results.append(result)
        
        return formatted_results
    
    def delete_by_source(self, source_doc: str):
        """
        Delete all chunks from a specific source document.
        
        Args:
            source_doc: Source document filename
        """
        self.collection.delete(
            where={"source_doc": source_doc}
        )
        print(f"Deleted chunks from {source_doc}")
    
    def clear(self):
        """Clear all data from the collection."""
        self.client.delete_collection(self.collection_name)
        self.collection = self.client.create_collection(
            name=self.collection_name,
            metadata={"description": "Financial tables from SEC filings"}
        )
        print("Vector store cleared")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about the vector store."""
        count = self.collection.count()
        
        # Get unique sources
        all_items = self.collection.get()
        unique_sources = set()
        unique_years = set()
        
        if all_items['metadatas']:
            for metadata in all_items['metadatas']:
                if 'source_doc' in metadata:
                    unique_sources.add(metadata['source_doc'])
                if 'year' in metadata:
                    unique_years.add(metadata['year'])
        
        return {
            'total_chunks': count,
            'unique_documents': len(unique_sources),
            'years': sorted(list(unique_years)),
            'sources': sorted(list(unique_sources))
        }


# Global vector store instance
_vector_store: Optional[VectorStore] = None


def get_vector_store() -> VectorStore:
    """Get or create global vector store instance."""
    global _vector_store
    if _vector_store is None:
        _vector_store = VectorStore()
    return _vector_store
