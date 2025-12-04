"""FAISS-based vector store for fast similarity search."""

import faiss
import numpy as np
import pickle
from pathlib import Path
from typing import List, Dict, Any, Optional, Iterable, Type
import os
import uuid

from langchain_core.vectorstores import VectorStore
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings

from config.settings import settings
from src.models.schemas import TableChunk
from src.embeddings.manager import get_embedding_manager
from src.utils import get_logger

logger = get_logger(__name__)


class FAISSVectorStore(VectorStore):
    """
    FAISS-based vector store for fast similarity search.
    
    Advantages over ChromaDB:
    - Faster similarity search for large datasets
    - Lower memory footprint
    - Optimized for high-dimensional vectors
    """
    
    def __init__(
        self, 
        embedding_function: Embeddings,
        dimension: int = None,
        persist_dir: str = None,
        index_type: str = "flat"
    ):
        """
        Initialize FAISS vector store.
        
        Args:
            embedding_function: LangChain embeddings interface
            dimension: Vector dimension (auto-detected if not provided)
            persist_dir: Directory to persist index
            index_type: Type of FAISS index (flat, ivf, hnsw)
        """
        self.embedding_function = embedding_function
        self.persist_dir = persist_dir or os.path.join(settings.PROJECT_ROOT, "faiss_index")
        self.index_type = index_type
        
        Path(self.persist_dir).mkdir(parents=True, exist_ok=True)
        
        # Auto-detect dimension from embedding manager if not provided
        if dimension is not None:
            self.dimension = dimension
        elif hasattr(embedding_function, 'get_dimension'):
            # Use dynamic dimension from embedding manager
            self.dimension = embedding_function.get_dimension()
        else:
            # Fallback to settings
            self.dimension = settings.EMBEDDING_DIMENSION
        
        # Initialize FAISS index
        self.index = self._create_index()
        self.metadata = []
        self.documents = []
        self.ids = []
        
        # Try to load existing index
        if self._index_exists():
            self.load()
        
        logger.info(f"FAISS vector store initialized: {self.persist_dir}")
        logger.info(f"Index type: {self.index_type}, Dimension: {self.dimension}")
    
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
    
    def add_texts(
        self,
        texts: Iterable[str],
        metadatas: Optional[List[dict]] = None,
        ids: Optional[List[str]] = None,
        **kwargs: Any,
    ) -> List[str]:
        """Run more texts through the embeddings and add to the vectorstore."""
        if not texts:
            return []
            
        # Generate embeddings
        embeddings = self.embedding_function.embed_documents(list(texts))
        
        # Add to index
        return self._add_vectors(embeddings, texts, metadatas, ids)

    def _add_vectors(
        self,
        embeddings: List[List[float]],
        texts: Iterable[str],
        metadatas: Optional[List[dict]] = None,
        ids: Optional[List[str]] = None,
    ) -> List[str]:
        """Add vectors to the store."""
        if ids is None:
            ids = [str(uuid.uuid4()) for _ in texts]
            
        if metadatas is None:
            metadatas = [{} for _ in texts]
            
        # Normalize embeddings for cosine similarity
        norm_embeddings = []
        for emb in embeddings:
            emb_np = np.array(emb, dtype='float32')
            emb_np = emb_np / np.linalg.norm(emb_np)
            norm_embeddings.append(emb_np)
            
        # Store data
        self.ids.extend(ids)
        self.metadata.extend(metadatas)
        self.documents.extend(texts)
        
        # Add to FAISS index
        embeddings_matrix = np.vstack(norm_embeddings)
        self.index.add(embeddings_matrix)
        
        logger.info(f"Added {len(texts)} chunks to FAISS index (total: {self.index.ntotal})")
        self.save()
        return ids

    def add_chunks(self, chunks: List, show_progress: bool = True):
        """
        Add chunks to FAISS index (Legacy wrapper for compatibility).
        
        Args:
            chunks: List of chunk objects
            show_progress: Show progress bar
        """
        if not chunks:
            return
            
        texts = []
        metadatas = []
        ids = []
        embeddings = []
        
        for chunk in chunks:
            texts.append(chunk.content)
            ids.append(chunk.chunk_id)
            
            # Handle metadata
            if isinstance(chunk.metadata, dict):
                metadatas.append(chunk.metadata)
            else:
                metadatas.append(chunk.metadata.dict())
                
            # Use pre-computed embedding if available
            if hasattr(chunk, 'embedding') and chunk.embedding:
                embeddings.append(chunk.embedding)
        
        if embeddings:
            # Use pre-computed embeddings
            self._add_vectors(embeddings, texts, metadatas, ids)
        else:
            # Generate embeddings
            self.add_texts(texts, metadatas, ids)

    def similarity_search(
        self,
        query: str,
        k: int = 4,
        filter: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> List[Document]:
        """Return docs most similar to query."""
        embedding = self.embedding_function.embed_query(query)
        docs_and_scores = self.similarity_search_by_vector_with_score(
            embedding, k, filter=filter
        )
        return [doc for doc, _ in docs_and_scores]

    def similarity_search_by_vector(
        self,
        embedding: List[float],
        k: int = 4,
        filter: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> List[Document]:
        """Return docs most similar to embedding vector."""
        docs_and_scores = self.similarity_search_by_vector_with_score(
            embedding, k, filter=filter
        )
        return [doc for doc, _ in docs_and_scores]

    def similarity_search_with_score(
        self,
        query: str,
        k: int = 4,
        filter: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> List[tuple[Document, float]]:
        """Run similarity search with distance."""
        embedding = self.embedding_function.embed_query(query)
        return self.similarity_search_by_vector_with_score(
            embedding, k, filter=filter
        )

    def search(
        self,
        query: str,
        top_k: int = 5,
        filters: Optional[Dict[str, Any]] = None
    ) -> List["SearchResult"]:
        """
        Search vector store.
        
        Args:
            query: Search query
            top_k: Number of results
            filters: Metadata filters
            
        Returns:
            List of SearchResult objects
        """
        from src.models.schemas import SearchResult, TableMetadata
        
        # Use similarity_search_with_score
        docs_and_scores = self.similarity_search_with_score(
            query,
            k=top_k,
            filter=filters
        )
        
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

    def similarity_search_by_vector_with_score(
        self,
        embedding: List[float],
        k: int = 4,
        filter: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> List[tuple[Document, float]]:
        """
        Return docs most similar to embedding vector, with score.
        """
        # Normalize query embedding
        query = np.array([embedding], dtype='float32')
        query = query / np.linalg.norm(query)
        
        # Search FAISS index
        # Get more results if filtering to ensure we have enough after filtering
        search_k = k * 3 if filter else k
        distances, indices = self.index.search(query, min(search_k, self.index.ntotal))
        
        results = []
        for i, idx in enumerate(indices[0]):
            if idx < 0 or idx >= len(self.documents):
                continue
            
            # Check filters
            metadata = self.metadata[idx]
            if filter:
                if not self._matches_filters(metadata, filter):
                    continue
            
            doc = Document(
                page_content=self.documents[idx],
                metadata=metadata
            )
            score = float(distances[0][i])
            
            results.append((doc, score))
            
            if len(results) >= k:
                break
                
        return results
    
    def _matches_filters(self, metadata: Dict[str, Any], filters: Dict[str, Any]) -> bool:
        """Check if metadata matches all filters."""
        for key, value in filters.items():
            if key not in metadata or metadata[key] != value:
                return False
        return True
    
    @classmethod
    def from_texts(
        cls,
        texts: List[str],
        embedding: Embeddings,
        metadatas: Optional[List[dict]] = None,
        **kwargs: Any,
    ) -> "FAISSVectorStore":
        """Construct FAISS wrapper from raw documents."""
        faiss_store = cls(embedding_function=embedding, **kwargs)
        faiss_store.add_texts(texts, metadatas, **kwargs)
        return faiss_store

    def delete_by_source(self, source_doc: str):
        """
        Delete all chunks from a specific source document.
        """
        # Find indices to keep
        keep_indices = [
            i for i, meta in enumerate(self.metadata)
            if meta.get('source_doc') != source_doc
        ]
        
        if len(keep_indices) == len(self.metadata):
            logger.warning(f"No chunks found from {source_doc}")
            return
        
        # Rebuild index with remaining items
        self.metadata = [self.metadata[i] for i in keep_indices]
        self.documents = [self.documents[i] for i in keep_indices]
        self.ids = [self.ids[i] for i in keep_indices]
        
        # Recreate index
        self.index = self._create_index()
        
        # Re-add embeddings (we need to regenerate them if we don't store them)
        # For now, we assume this is a rare operation or we accept re-indexing.
        # A better approach would be to store vectors or use FAISS remove_ids (if supported by index type)
        logger.info(f"Deleted chunks from {source_doc}. Index cleared (re-indexing required).")
        self.save()
    
    def clear(self):
        """Clear all data from the index."""
        self.index = self._create_index()
        self.metadata = []
        self.documents = []
        self.ids = []
        logger.info("FAISS index cleared")
        self.save()
    
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
        
        logger.info(f"FAISS index saved to {self.persist_dir}")
    
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
            
            logger.info(f"FAISS index loaded from {self.persist_dir} ({self.index.ntotal} vectors)")
        except Exception as e:
            logger.error(f"Failed to load FAISS index: {e}")
            logger.warning("Starting with empty index")


# Global FAISS store instance
_faiss_store: Optional[FAISSVectorStore] = None


def get_faiss_store() -> FAISSVectorStore:
    """Get or create global FAISS store instance."""
    global _faiss_store
    if _faiss_store is None:
        embedding_manager = get_embedding_manager()
        _faiss_store = FAISSVectorStore(embedding_function=embedding_manager)
    return _faiss_store
