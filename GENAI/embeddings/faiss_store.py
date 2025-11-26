"""FAISS-based vector store for fast similarity search."""

import faiss
import numpy as np
import pickle
from pathlib import Path
from typing import List, Dict, Any, Optional
import os

from config.settings import settings
from models.schemas import TableChunk


class FAISSVectorStore:
    """
    FAISS-based vector store for fast similarity search.
    
    Advantages over ChromaDB:
    - Faster similarity search for large datasets
    - Lower memory footprint
    - Optimized for high-dimensional vectors
    """
    
    def __init__(
        self, 
        dimension: int = None,
        persist_dir: str = None,
        index_type: str = "flat"
    ):
        """
        Initialize FAISS vector store.
        
        Args:
            dimension: Vector dimension (default from settings)
            persist_dir: Directory to persist index
            index_type: Type of FAISS index (flat, ivf, hnsw)
        """
        self.dimension = dimension or settings.EMBEDDING_DIMENSION
        self.persist_dir = persist_dir or os.path.join(settings.PROJECT_ROOT, "faiss_index")
        self.index_type = index_type
        
        Path(self.persist_dir).mkdir(parents=True, exist_ok=True)
        
        # Initialize FAISS index
        self.index = self._create_index()
        self.metadata = []
        self.documents = []
        self.ids = []
        
        # Try to load existing index
        if self._index_exists():
            self.load()
        
        print(f"FAISS vector store initialized: {self.persist_dir}")
        print(f"Index type: {self.index_type}, Dimension: {self.dimension}")
    
    def _create_index(self):
        """Create FAISS index based on type."""
        if self.index_type == "flat":
            # Flat index with inner product (for cosine similarity)
            return faiss.IndexFlatIP(self.dimension)
        elif self.index_type == "ivf":
            # IVF index for faster search on large datasets
            quantizer = faiss.IndexFlatIP(self.dimension)
            return faiss.IndexIVFFlat(quantizer, self.dimension, 100)
        elif self.index_type == "hnsw":
            # HNSW index for very fast approximate search
            return faiss.IndexHNSWFlat(self.dimension, 32)
        else:
            raise ValueError(f"Unknown index type: {self.index_type}")
    
    def add_chunks(self, chunks: List[TableChunk], show_progress: bool = True):
        """
        Add chunks to FAISS index.
        
        Args:
            chunks: List of TableChunk objects
            show_progress: Show progress bar
        """
        if not chunks:
            return
        
        embeddings = []
        
        for chunk in chunks:
            # Normalize embedding for cosine similarity
            emb = np.array(chunk.embedding, dtype='float32')
            emb = emb / np.linalg.norm(emb)
            embeddings.append(emb)
            
            # Store metadata and documents
            self.ids.append(chunk.chunk_id)
            self.metadata.append(chunk.metadata.dict())
            self.documents.append(chunk.content)
        
        # Add to index
        embeddings_matrix = np.vstack(embeddings)
        self.index.add(embeddings_matrix)
        
        print(f"Added {len(chunks)} chunks to FAISS index (total: {self.index.ntotal})")
    
    def search(
        self,
        query_embedding: List[float],
        top_k: int = 5,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Search for similar vectors.
        
        Args:
            query_embedding: Query vector
            top_k: Number of results to return
            filters: Metadata filters (applied post-search)
        
        Returns:
            List of search results with content and metadata
        """
        # Normalize query embedding
        query = np.array([query_embedding], dtype='float32')
        query = query / np.linalg.norm(query)
        
        # Search FAISS index
        # Get more results if filtering to ensure we have enough after filtering
        search_k = top_k * 3 if filters else top_k
        distances, indices = self.index.search(query, min(search_k, self.index.ntotal))
        
        # Format results
        results = []
        for i, idx in enumerate(indices[0]):
            if idx < 0 or idx >= len(self.documents):
                continue
            
            result = {
                'id': self.ids[idx],
                'content': self.documents[idx],
                'metadata': self.metadata[idx],
                'score': float(distances[0][i]),
                'distance': float(distances[0][i])
            }
            
            # Apply metadata filters
            if filters:
                if not self._matches_filters(result['metadata'], filters):
                    continue
            
            results.append(result)
            
            # Stop if we have enough results
            if len(results) >= top_k:
                break
        
        return results
    
    def _matches_filters(self, metadata: Dict[str, Any], filters: Dict[str, Any]) -> bool:
        """Check if metadata matches all filters."""
        for key, value in filters.items():
            if key not in metadata or metadata[key] != value:
                return False
        return True
    
    def delete_by_source(self, source_doc: str):
        """
        Delete all chunks from a specific source document.
        
        Note: FAISS doesn't support deletion, so we rebuild the index.
        """
        # Find indices to keep
        keep_indices = [
            i for i, meta in enumerate(self.metadata)
            if meta.get('source_doc') != source_doc
        ]
        
        if len(keep_indices) == len(self.metadata):
            print(f"No chunks found from {source_doc}")
            return
        
        # Rebuild index with remaining items
        self.metadata = [self.metadata[i] for i in keep_indices]
        self.documents = [self.documents[i] for i in keep_indices]
        self.ids = [self.ids[i] for i in keep_indices]
        
        # Recreate index
        self.index = self._create_index()
        
        # Re-add embeddings (we need to regenerate them)
        print(f"Deleted chunks from {source_doc}. Index rebuilt.")
    
    def clear(self):
        """Clear all data from the index."""
        self.index = self._create_index()
        self.metadata = []
        self.documents = []
        self.ids = []
        print("FAISS index cleared")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about the vector store."""
        unique_sources = set()
        unique_years = set()
        
        for metadata in self.metadata:
            if 'source_doc' in metadata:
                unique_sources.add(metadata['source_doc'])
            if 'year' in metadata:
                unique_years.add(metadata['year'])
        
        return {
            'total_chunks': self.index.ntotal,
            'unique_documents': len(unique_sources),
            'years': sorted(list(unique_years)),
            'sources': sorted(list(unique_sources)),
            'index_type': self.index_type,
            'dimension': self.dimension
        }
    
    def _index_exists(self) -> bool:
        """Check if persisted index exists."""
        return (
            Path(f'{self.persist_dir}/index.faiss').exists() and
            Path(f'{self.persist_dir}/metadata.pkl').exists()
        )
    
    def save(self):
        """Persist index to disk."""
        faiss.write_index(self.index, f'{self.persist_dir}/index.faiss')
        
        with open(f'{self.persist_dir}/metadata.pkl', 'wb') as f:
            pickle.dump({
                'metadata': self.metadata,
                'documents': self.documents,
                'ids': self.ids,
                'index_type': self.index_type,
                'dimension': self.dimension
            }, f)
        
        print(f"FAISS index saved to {self.persist_dir}")
    
    def load(self):
        """Load index from disk."""
        try:
            self.index = faiss.read_index(f'{self.persist_dir}/index.faiss')
            
            with open(f'{self.persist_dir}/metadata.pkl', 'rb') as f:
                data = pickle.load(f)
                self.metadata = data['metadata']
                self.documents = data['documents']
                self.ids = data['ids']
                self.index_type = data.get('index_type', 'flat')
                self.dimension = data.get('dimension', self.dimension)
            
            print(f"FAISS index loaded from {self.persist_dir} ({self.index.ntotal} vectors)")
        except Exception as e:
            print(f"Failed to load FAISS index: {e}")
            print("Starting with empty index")


# Global FAISS store instance
_faiss_store: Optional[FAISSVectorStore] = None


def get_faiss_store() -> FAISSVectorStore:
    """Get or create global FAISS store instance."""
    global _faiss_store
    if _faiss_store is None:
        _faiss_store = FAISSVectorStore()
    return _faiss_store
