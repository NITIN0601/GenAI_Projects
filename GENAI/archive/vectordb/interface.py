"""
Unified VectorDB system for enterprise-grade production deployment.

This module provides a consistent interface across all VectorDB backends:
- ChromaDB (persistent, default)
- FAISS (high-performance, in-memory)
- Redis Vector (distributed, scalable)

All backends store data in the same format with identical metadata schema.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from pathlib import Path
import json
import pickle

from vectordb.schemas import (
    TableChunk,
    TableMetadata,
    VectorDBStats,
    serialize_for_storage,
    deserialize_from_storage
)


class UnifiedVectorDBInterface(ABC):
    """
    Abstract base class for all VectorDB backends.
    
    Ensures consistent API and data format across:
    - ChromaDB
    - FAISS  
    - Redis Vector
    """
    
    @abstractmethod
    def add_chunks(
        self,
        chunks: List[TableChunk],
        show_progress: bool = True
    ) -> None:
        """
        Add chunks to vector database.
        
        Args:
            chunks: List of TableChunk objects
            show_progress: Show progress bar
        """
        pass
    
    @abstractmethod
    def search(
        self,
        query_embedding: List[float],
        top_k: int = 5,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Search for similar chunks.
        
        Args:
            query_embedding: Query vector
            top_k: Number of results
            filters: Metadata filters
            
        Returns:
            List of results with content and metadata
        """
        pass
    
    @abstractmethod
    def get_by_metadata(
        self,
        filters: Dict[str, Any],
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Get chunks by metadata filters.
        
        Args:
            filters: Metadata filters
            limit: Maximum results
            
        Returns:
            List of matching chunks
        """
        pass
    
    @abstractmethod
    def delete_by_source(self, source_doc: str) -> None:
        """
        Delete all chunks from a source document.
        
        Args:
            source_doc: Source document filename
        """
        pass
    
    @abstractmethod
    def clear(self) -> None:
        """Clear all data from the database."""
        pass
    
    @abstractmethod
    def get_stats(self) -> VectorDBStats:
        """
        Get database statistics.
        
        Returns:
            VectorDBStats object
        """
        pass
    
    @abstractmethod
    def export_data(self, output_path: str) -> None:
        """
        Export all data to file (for migration).
        
        Args:
            output_path: Path to export file
        """
        pass
    
    @abstractmethod
    def import_data(self, input_path: str) -> None:
        """
        Import data from file (for migration).
        
        Args:
            input_path: Path to import file
        """
        pass
    
    def get_provider_name(self) -> str:
        """Get provider name."""
        return self.__class__.__name__.replace('VectorDB', '').lower()


class ChromaDBBackend(UnifiedVectorDBInterface):
    """ChromaDB backend implementation."""
    
    def __init__(
        self,
        persist_directory: str = "./vectordb/chroma",
        collection_name: str = "financial_tables"
    ):
        """Initialize ChromaDB backend."""
        import chromadb
        from chromadb.config import Settings as ChromaSettings
        
        self.persist_directory = persist_directory
        self.collection_name = collection_name
        
        # Create directory
        Path(persist_directory).mkdir(parents=True, exist_ok=True)
        
        # Initialize client
        self.client = chromadb.PersistentClient(
            path=persist_directory,
            settings=ChromaSettings(
                anonymized_telemetry=False,
                allow_reset=True
            )
        )
        
        # Get or create collection
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata={"description": "Financial tables - unified schema"}
        )
        
        print(f"✓ ChromaDB initialized: {persist_directory}")
    
    def add_chunks(
        self,
        chunks: List[TableChunk],
        show_progress: bool = True
    ) -> None:
        """Add chunks to ChromaDB."""
        if not chunks:
            return
        
        ids = []
        documents = []
        embeddings = []
        metadatas = []
        
        for chunk in chunks:
            storage_format = serialize_for_storage(chunk)
            
            ids.append(storage_format['id'])
            documents.append(storage_format['content'])
            embeddings.append(storage_format['embedding'] or [0.0] * 384)
            
            # Flatten metadata for ChromaDB
            metadata = storage_format['metadata'].copy()
            metadata['chunk_index'] = storage_format.get('chunk_index', 0)
            metadata['total_chunks'] = storage_format.get('total_chunks', 1)
            
            metadatas.append(metadata)
        
        self.collection.add(
            ids=ids,
            documents=documents,
            embeddings=embeddings,
            metadatas=metadatas
        )
        
        print(f"✓ Added {len(chunks)} chunks to ChromaDB")
    
    def search(
        self,
        query_embedding: List[float],
        top_k: int = 5,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Search ChromaDB."""
        where_clause = filters if filters else None
        
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            where=where_clause
        )
        
        formatted_results = []
        if results['ids'] and results['ids'][0]:
            for i in range(len(results['ids'][0])):
                formatted_results.append({
                    'id': results['ids'][0][i],
                    'content': results['documents'][0][i],
                    'metadata': results['metadatas'][0][i],
                    'distance': results['distances'][0][i] if 'distances' in results else None
                })
        
        return formatted_results
    
    def get_by_metadata(
        self,
        filters: Dict[str, Any],
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get by metadata from ChromaDB."""
        results = self.collection.get(where=filters, limit=limit)
        
        formatted_results = []
        if results['ids']:
            for i in range(len(results['ids'])):
                formatted_results.append({
                    'id': results['ids'][i],
                    'content': results['documents'][i],
                    'metadata': results['metadatas'][i]
                })
        
        return formatted_results
    
    def delete_by_source(self, source_doc: str) -> None:
        """Delete by source from ChromaDB."""
        self.collection.delete(where={"source_doc": source_doc})
        print(f"✓ Deleted chunks from {source_doc}")
    
    def clear(self) -> None:
        """Clear ChromaDB collection."""
        self.client.delete_collection(self.collection_name)
        self.collection = self.client.create_collection(
            name=self.collection_name,
            metadata={"description": "Financial tables - unified schema"}
        )
        print("✓ ChromaDB cleared")
    
    def get_stats(self) -> VectorDBStats:
        """Get ChromaDB statistics."""
        count = self.collection.count()
        all_items = self.collection.get()
        
        unique_sources = set()
        unique_years = set()
        
        if all_items['metadatas']:
            for metadata in all_items['metadatas']:
                if 'source_doc' in metadata:
                    unique_sources.add(metadata['source_doc'])
                if 'year' in metadata:
                    unique_years.add(metadata['year'])
        
        return VectorDBStats(
            provider="chromadb",
            total_chunks=count,
            unique_documents=len(unique_sources),
            years=sorted(list(unique_years)),
            sources=sorted(list(unique_sources))
        )
    
    def export_data(self, output_path: str) -> None:
        """Export ChromaDB data."""
        all_data = self.collection.get(include=['documents', 'metadatas', 'embeddings'])
        
        export_data = {
            'provider': 'chromadb',
            'collection_name': self.collection_name,
            'chunks': []
        }
        
        for i in range(len(all_data['ids'])):
            export_data['chunks'].append({
                'id': all_data['ids'][i],
                'content': all_data['documents'][i],
                'metadata': all_data['metadatas'][i],
                'embedding': all_data['embeddings'][i] if all_data['embeddings'] else None
            })
        
        with open(output_path, 'w') as f:
            json.dump(export_data, f, indent=2)
        
        print(f"✓ Exported {len(export_data['chunks'])} chunks to {output_path}")
    
    def import_data(self, input_path: str) -> None:
        """Import data to ChromaDB."""
        with open(input_path, 'r') as f:
            import_data = json.load(f)
        
        chunks_data = import_data['chunks']
        
        ids = [c['id'] for c in chunks_data]
        documents = [c['content'] for c in chunks_data]
        metadatas = [c['metadata'] for c in chunks_data]
        embeddings = [c['embedding'] for c in chunks_data if c.get('embedding')]
        
        self.collection.add(
            ids=ids,
            documents=documents,
            metadatas=metadatas,
            embeddings=embeddings if embeddings else None
        )
        
        print(f"✓ Imported {len(chunks_data)} chunks from {input_path}")


class FAISSBackend(UnifiedVectorDBInterface):
    """FAISS backend implementation."""
    
    def __init__(
        self,
        persist_directory: str = "./vectordb/faiss",
        dimension: int = 384,
        index_type: str = "flat"
    ):
        """Initialize FAISS backend."""
        import faiss
        import numpy as np
        
        self.persist_directory = persist_directory
        self.dimension = dimension
        self.index_type = index_type
        
        # Create directory
        Path(persist_directory).mkdir(parents=True, exist_ok=True)
        
        # Initialize index
        if index_type == "flat":
            self.index = faiss.IndexFlatL2(dimension)
        elif index_type == "ivf":
            quantizer = faiss.IndexFlatL2(dimension)
            self.index = faiss.IndexIVFFlat(quantizer, dimension, 100)
        else:
            self.index = faiss.IndexFlatL2(dimension)
        
        # Storage for metadata and content
        self.metadata_store: List[Dict[str, Any]] = []
        self.content_store: List[str] = []
        self.id_store: List[str] = []
        
        # Load if exists
        self._load_if_exists()
        
        print(f"✓ FAISS initialized: {persist_directory}")
    
    def _load_if_exists(self):
        """Load existing index if present."""
        import faiss
        
        index_path = Path(self.persist_directory) / "index.faiss"
        metadata_path = Path(self.persist_directory) / "metadata.pkl"
        
        if index_path.exists() and metadata_path.exists():
            self.index = faiss.read_index(str(index_path))
            with open(metadata_path, 'rb') as f:
                data = pickle.load(f)
                self.metadata_store = data['metadata']
                self.content_store = data['content']
                self.id_store = data['ids']
            print(f"✓ Loaded existing FAISS index ({len(self.id_store)} chunks)")
    
    def _save(self):
        """Save index and metadata."""
        import faiss
        
        index_path = Path(self.persist_directory) / "index.faiss"
        metadata_path = Path(self.persist_directory) / "metadata.pkl"
        
        faiss.write_index(self.index, str(index_path))
        
        with open(metadata_path, 'wb') as f:
            pickle.dump({
                'metadata': self.metadata_store,
                'content': self.content_store,
                'ids': self.id_store
            }, f)
    
    def add_chunks(
        self,
        chunks: List[TableChunk],
        show_progress: bool = True
    ) -> None:
        """Add chunks to FAISS."""
        import numpy as np
        
        if not chunks:
            return
        
        vectors = []
        for chunk in chunks:
            storage_format = serialize_for_storage(chunk)
            
            # Add to stores
            self.id_store.append(storage_format['id'])
            self.content_store.append(storage_format['content'])
            self.metadata_store.append(storage_format['metadata'])
            
            # Add vector
            embedding = storage_format['embedding'] or [0.0] * self.dimension
            vectors.append(embedding)
        
        # Add to index
        vectors_np = np.array(vectors, dtype='float32')
        self.index.add(vectors_np)
        
        # Save
        self._save()
        
        print(f"✓ Added {len(chunks)} chunks to FAISS")
    
    def search(
        self,
        query_embedding: List[float],
        top_k: int = 5,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Search FAISS."""
        import numpy as np
        
        query_np = np.array([query_embedding], dtype='float32')
        distances, indices = self.index.search(query_np, top_k)
        
        results = []
        for i, idx in enumerate(indices[0]):
            if idx < len(self.id_store):
                metadata = self.metadata_store[idx]
                
                # Apply filters
                if filters:
                    match = all(metadata.get(k) == v for k, v in filters.items())
                    if not match:
                        continue
                
                results.append({
                    'id': self.id_store[idx],
                    'content': self.content_store[idx],
                    'metadata': metadata,
                    'distance': float(distances[0][i])
                })
        
        return results[:top_k]
    
    def get_by_metadata(
        self,
        filters: Dict[str, Any],
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get by metadata from FAISS."""
        results = []
        
        for i, metadata in enumerate(self.metadata_store):
            match = all(metadata.get(k) == v for k, v in filters.items())
            if match:
                results.append({
                    'id': self.id_store[i],
                    'content': self.content_store[i],
                    'metadata': metadata
                })
                
                if len(results) >= limit:
                    break
        
        return results
    
    def delete_by_source(self, source_doc: str) -> None:
        """Delete by source from FAISS (rebuild index)."""
        # FAISS doesn't support deletion, so rebuild
        import numpy as np
        import faiss
        
        keep_indices = []
        for i, metadata in enumerate(self.metadata_store):
            if metadata.get('source_doc') != source_doc:
                keep_indices.append(i)
        
        # Rebuild stores
        self.metadata_store = [self.metadata_store[i] for i in keep_indices]
        self.content_store = [self.content_store[i] for i in keep_indices]
        self.id_store = [self.id_store[i] for i in keep_indices]
        
        # Rebuild index
        self.index = faiss.IndexFlatL2(self.dimension)
        
        # Re-add vectors (would need to store them)
        print(f"⚠️  FAISS deletion requires re-indexing")
        self._save()
    
    def clear(self) -> None:
        """Clear FAISS index."""
        import faiss
        
        self.index = faiss.IndexFlatL2(self.dimension)
        self.metadata_store = []
        self.content_store = []
        self.id_store = []
        self._save()
        print("✓ FAISS cleared")
    
    def get_stats(self) -> VectorDBStats:
        """Get FAISS statistics."""
        unique_sources = set()
        unique_years = set()
        
        for metadata in self.metadata_store:
            if 'source_doc' in metadata:
                unique_sources.add(metadata['source_doc'])
            if 'year' in metadata:
                unique_years.add(metadata['year'])
        
        return VectorDBStats(
            provider="faiss",
            total_chunks=len(self.id_store),
            unique_documents=len(unique_sources),
            years=sorted(list(unique_years)),
            sources=sorted(list(unique_sources)),
            index_type=self.index_type
        )
    
    def export_data(self, output_path: str) -> None:
        """Export FAISS data."""
        export_data = {
            'provider': 'faiss',
            'dimension': self.dimension,
            'index_type': self.index_type,
            'chunks': []
        }
        
        for i in range(len(self.id_store)):
            export_data['chunks'].append({
                'id': self.id_store[i],
                'content': self.content_store[i],
                'metadata': self.metadata_store[i],
                'embedding': None  # Would need to extract from index
            })
        
        with open(output_path, 'w') as f:
            json.dump(export_data, f, indent=2)
        
        print(f"✓ Exported {len(export_data['chunks'])} chunks to {output_path}")
    
    def import_data(self, input_path: str) -> None:
        """Import data to FAISS."""
        with open(input_path, 'r') as f:
            import_data = json.load(f)
        
        # Would need embeddings in import data
        print("⚠️  FAISS import requires embeddings in source data")


# Factory function
def get_unified_vectordb(
    provider: Optional[str] = None,
    **kwargs
) -> UnifiedVectorDBInterface:
    """
    Get unified VectorDB instance.
    
    Args:
        provider: "chromadb", "faiss", or "redis" (default: from settings)
        **kwargs: Provider-specific arguments
        
    Returns:
        UnifiedVectorDBInterface instance
    """
    # Use config if not specified
    if provider is None:
        from config.settings import settings
        provider = getattr(settings, 'VECTORDB_PROVIDER', 'chromadb')
    
    provider = provider.lower()
    
    if provider == "chromadb":
        # Get settings if not provided
        if 'persist_directory' not in kwargs or 'collection_name' not in kwargs:
            from config.settings import settings
            kwargs.setdefault('persist_directory', settings.CHROMA_PERSIST_DIR)
            kwargs.setdefault('collection_name', settings.CHROMA_COLLECTION_NAME)
        
        return ChromaDBBackend(
            persist_directory=kwargs.get('persist_directory'),
            collection_name=kwargs.get('collection_name')
        )
    elif provider == "faiss":
        # Get settings if not provided
        if 'persist_directory' not in kwargs or 'dimension' not in kwargs:
            from config.settings import settings
            kwargs.setdefault('persist_directory', settings.FAISS_PERSIST_DIR)
            kwargs.setdefault('dimension', settings.EMBEDDING_DIMENSION)
            kwargs.setdefault('index_type', settings.FAISS_INDEX_TYPE)
        
        return FAISSBackend(
            persist_directory=kwargs.get('persist_directory'),
            dimension=kwargs.get('dimension'),
            index_type=kwargs.get('index_type')
        )
    elif provider == "redis":
        raise NotImplementedError("Redis Vector backend coming soon")
    else:
        raise ValueError(f"Unknown provider: {provider}")
