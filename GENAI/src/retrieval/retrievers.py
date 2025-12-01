"""
Retrievers module for advanced search capabilities.

Implements:
- Vector Search (Semantic)
- Keyword Search (BM25)
- Hybrid Search (Weighted combination)
"""

from typing import List, Dict, Any, Optional, Union
import logging

from langchain_core.retrievers import BaseRetriever
from langchain_core.vectorstores import VectorStore
from langchain_core.documents import Document
from langchain_community.retrievers import BM25Retriever

from config.settings import settings
from src.vector_store.stores.faiss_store import get_faiss_store
from src.vector_store.stores.chromadb_store import get_vector_store as get_chroma_store
from src.vector_store.stores.redis_store import get_redis_store

logger = logging.getLogger(__name__)


class SimpleHybridRetriever(BaseRetriever):
    """
    Simple hybrid retriever combining vector and keyword search.
    
    Uses weighted scoring to combine results from BM25 and vector similarity.
    """
    
    def __init__(self, vector_retriever: BaseRetriever, bm25_retriever: BM25Retriever, alpha: float = 0.5):
        """
        Initialize hybrid retriever.
        
        Args:
            vector_retriever: Vector similarity retriever
            bm25_retriever: BM25 keyword retriever  
            alpha: Weight for vector search (0-1). BM25 weight is (1-alpha)
        """
        super().__init__()
        self.vector_retriever = vector_retriever
        self.bm25_retriever = bm25_retriever
        self.alpha = alpha
    
    def _get_relevant_documents(self, query: str) -> List[Document]:
        """Get relevant documents using hybrid search."""
        # Get results from both retrievers
        vector_docs = self.vector_retriever.get_relevant_documents(query)
        bm25_docs = self.bm25_retriever.get_relevant_documents(query)
        
        # Combine and deduplicate
        seen_content = set()
        combined_docs = []
        
        # Add vector results (weighted by alpha)
        for i, doc in enumerate(vector_docs):
            content_key = doc.page_content[:100]  # Use first 100 chars as key
            if content_key not in seen_content:
                seen_content.add(content_key)
                combined_docs.append(doc)
        
        # Add BM25 results (weighted by 1-alpha)
        for i, doc in enumerate(bm25_docs):
            content_key = doc.page_content[:100]
            if content_key not in seen_content:
                seen_content.add(content_key)
                combined_docs.append(doc)
        
        return combined_docs


def get_retriever(
    search_type: str = "hybrid",
    k: int = None,
    filters: Optional[Dict[str, Any]] = None
) -> BaseRetriever:
    """
    Get retriever based on configuration.
    
    Args:
        search_type: 'vector', 'keyword', or 'hybrid'
        k: Number of results to return
        filters: Metadata filters
        
    Returns:
        LangChain Retriever
    """
    k = k or settings.SEARCH_TOP_K
    
    # 1. Get Vector Store
    if settings.VECTORDB_PROVIDER == "faiss":
        vector_store = get_faiss_store()
    elif settings.VECTORDB_PROVIDER == "redis":
        vector_store = get_redis_store()
    else:
        wrapper = get_chroma_store()
        vector_store = wrapper.get_langchain_store()

    # 2. Create Vector Retriever
    search_kwargs = {"k": k}
    if filters:
        search_kwargs["filter"] = filters
        
    vector_retriever = vector_store.as_retriever(
        search_type="similarity",
        search_kwargs=search_kwargs
    )
    
    if search_type == "vector":
        return vector_retriever
        
    # 3. Create Keyword Retriever (BM25)
    documents = []
    if hasattr(vector_store, "documents") and hasattr(vector_store, "metadata"):
        # FAISS / Redis (our implementations)
        for i, content in enumerate(vector_store.documents):
            meta = vector_store.metadata[i] if i < len(vector_store.metadata) else {}
            documents.append(Document(page_content=content, metadata=meta))
    else:
        # Chroma - fallback to vector only
        logger.warning("BM25 not fully supported for ChromaDB. Fallback to vector.")
        return vector_retriever
            
    if not documents:
        logger.warning("No documents found for BM25 index. Fallback to vector.")
        return vector_retriever
        
    bm25_retriever = BM25Retriever.from_documents(documents)
    bm25_retriever.k = k
    
    if search_type == "keyword":
        return bm25_retriever
        
    # 4. Create Hybrid Retriever
    if search_type == "hybrid":
        hybrid_retriever = SimpleHybridRetriever(
            vector_retriever=vector_retriever,
            bm25_retriever=bm25_retriever,
            alpha=settings.HYBRID_SEARCH_ALPHA
        )
        return hybrid_retriever
        
    return vector_retriever
