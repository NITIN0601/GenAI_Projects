"""
Redis Vector Store implementation.

Supports distributed vector search using Redis Stack.
"""

from typing import List, Dict, Any, Optional, Iterable, Type
import json
import numpy as np
import logging
import uuid

from langchain_core.vectorstores import VectorStore
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings

from config.settings import settings
from src.domain.tables import TableChunk
from src.utils import get_logger
from src.infrastructure.embeddings.manager import get_embedding_manager

logger = get_logger(__name__)

try:
    import redis
    from redis.commands.search.field import VectorField, TagField, TextField
    from redis.commands.search.indexDefinition import IndexDefinition, IndexType
    from redis.commands.search.query import Query
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False


class RedisVectorStore(VectorStore):
    """Redis Vector Store implementation."""
    
    def __init__(
        self, 
        embedding_function: Embeddings,
        index_name: str = "financial_docs"
    ):
        """Initialize Redis Vector Store."""
        if not REDIS_AVAILABLE:
            raise ImportError("redis-py not installed. Install with: pip install redis")
            
        self.client = redis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            password=settings.REDIS_PASSWORD,
            decode_responses=True
        )
        self.index_name = index_name
        self.embedding_function = embedding_function
        self.dimension = settings.EMBEDDING_DIMENSION
        
        self._create_index()
        logger.info(f"Redis Vector Store initialized: {index_name}")

    def _create_index(self):
        """Create search index if not exists."""
        try:
            self.client.ft(self.index_name).info()
            logger.info(f"Using existing index: {self.index_name}")
        except Exception:
            # Index doesn't exist, create it
            # NOTE: This schema must match TableMetadata fields for full parity
            from redis.commands.search.field import NumericField
            
            schema = (
                # Content
                TextField("content"),
                
                # === Core Document Info ===
                TagField("source_doc"),
                TagField("table_id"),
                TagField("chunk_reference_id"),
                NumericField("page_no"),
                TextField("table_title"),
                TextField("original_table_title"),
                
                # === Company Info ===
                TextField("company_name"),
                TagField("company_ticker"),
                
                # === Temporal Info ===
                TagField("year"),
                TagField("quarter"),
                TagField("quarter_number"),
                TagField("month"),
                TagField("report_type"),
                TextField("fiscal_period"),
                
                # === Table Classification ===
                TagField("table_type"),
                TagField("statement_type"),
                NumericField("chunk_table_index"),
                NumericField("table_start_page"),
                NumericField("table_end_page"),
                
                # === Table Structure ===
                TextField("column_headers"),
                TextField("row_headers"),
                NumericField("column_count"),
                NumericField("row_count"),
                
                # === Multi-level Headers ===
                TagField("has_multi_level_headers"),
                TextField("main_header"),
                TextField("sub_headers"),
                
                # === Hierarchical Structure ===
                TextField("parent_section"),
                TagField("has_hierarchy"),
                TextField("subsections"),
                TagField("table_structure"),
                
                # === Financial Context ===
                TagField("units"),
                TagField("currency"),
                TagField("has_currency"),
                NumericField("currency_count"),
                
                # === Extraction Info ===
                TagField("extraction_backend"),
                NumericField("quality_score"),
                NumericField("extraction_confidence"),
                
                # === Embedding Info ===
                TagField("embedding_model"),
                NumericField("embedding_dimension"),
                TagField("embedding_provider"),
                
                # Vector
                VectorField(
                    "embedding",
                    "FLAT",
                    {
                        "TYPE": "FLOAT32",
                        "DIM": self.dimension,
                        "DISTANCE_METRIC": "COSINE",
                    }
                ),
            )
            definition = IndexDefinition(prefix=["doc:"], index_type=IndexType.HASH)
            self.client.ft(self.index_name).create_index(schema, definition=definition)
            logger.info(f"Created index: {self.index_name} with comprehensive TableMetadata schema")

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
            
        pipeline = self.client.pipeline()
        for i, text in enumerate(texts):
            key = f"doc:{ids[i]}"
            
            # Prepare mapping
            mapping = {
                "content": text,
                "embedding": np.array(embeddings[i], dtype=np.float32).tobytes(),
                **metadatas[i]
            }
            
            pipeline.hset(key, mapping=mapping)
            
        pipeline.execute()
        logger.info(f"Added {len(texts)} chunks to Redis Vector")
        return ids

    def add_chunks(self, chunks: List[TableChunk]):
        """Add chunks to Redis (Legacy wrapper)."""
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
            self._add_vectors(embeddings, texts, metadatas, ids)
        else:
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
        from src.domain import SearchResult, TableMetadata
        
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
        
        Returns ALL metadata fields (30+) for parity with FAISS/ChromaDB.
        """
        base_query = f"*=>[KNN {k} @embedding $vec_param AS vector_score]"
        
        # Return ALL fields by not specifying return_fields
        # This ensures we get the complete metadata (30+ fields)
        query = Query(base_query)\
            .sort_by("vector_score")\
            .paging(0, k)\
            .dialect(2)
            
        params = {
            "vec_param": np.array(embedding, dtype=np.float32).tobytes()
        }
        
        try:
            results = self.client.ft(self.index_name).search(query, query_params=params)
            
            processed_results = []
            for doc in results.docs:
                # Reconstruct full metadata from ALL Redis fields
                # Redis returns fields as attributes on the doc object
                metadata = {}
                
                # Get all attributes except internal ones
                for attr in dir(doc):
                    if not attr.startswith('_') and attr not in ['id', 'payload']:
                        try:
                            value = getattr(doc, attr, None)
                            # Skip the content and embedding fields (already handled)
                            if attr not in ['content', 'embedding', 'vector_score']:
                                # Handle numeric strings
                                if isinstance(value, str):
                                    # Try to convert numeric strings back to numbers
                                    if value.isdigit():
                                        metadata[attr] = int(value)
                                    elif value.replace('.', '', 1).isdigit():
                                        metadata[attr] = float(value)
                                    else:
                                        metadata[attr] = value
                                else:
                                    metadata[attr] = value
                        except Exception:
                            continue
                
                # Ensure critical fields exist (even if empty)
                metadata.setdefault('source_doc', '')
                metadata.setdefault('actual_table_title', '')
                metadata.setdefault('year', None)
                metadata.setdefault('quarter', None)
                
                document = Document(
                    page_content=doc.content,
                    metadata=metadata  # Now contains ALL 30+ fields
                )
                score = float(doc.vector_score)
                processed_results.append((document, score))
                
            logger.info(f"Redis search returned {len(processed_results)} results with full metadata")
            return processed_results
            
        except Exception as e:
            logger.error(f"Redis search failed: {e}")
            return []
    
    @classmethod
    def from_texts(
        cls,
        texts: List[str],
        embedding: Embeddings,
        metadatas: Optional[List[dict]] = None,
        **kwargs: Any,
    ) -> "RedisVectorStore":
        """Construct Redis wrapper from raw documents."""
        store = cls(embedding_function=embedding, **kwargs)
        store.add_texts(texts, metadatas, **kwargs)
        return store

# Thread-safe module-level singleton
_redis_store: Optional[RedisVectorStore] = None
_redis_lock = None

def _get_redis_lock():
    """Get or create the singleton lock."""
    global _redis_lock
    if _redis_lock is None:
        import threading
        _redis_lock = threading.Lock()
    return _redis_lock


def get_redis_store() -> RedisVectorStore:
    """
    Get or create global Redis store instance.
    
    Thread-safe singleton accessor.
    
    Returns:
        RedisVectorStore singleton instance
    """
    global _redis_store
    
    if _redis_store is not None:
        return _redis_store
    
    with _get_redis_lock():
        if _redis_store is None:
            embedding_manager = get_embedding_manager()
            _redis_store = RedisVectorStore(embedding_function=embedding_manager)
        return _redis_store


def reset_redis_store() -> None:
    """
    Reset the Redis store singleton.
    
    Useful for testing or reconfiguration.
    """
    global _redis_store
    with _get_redis_lock():
        _redis_store = None

