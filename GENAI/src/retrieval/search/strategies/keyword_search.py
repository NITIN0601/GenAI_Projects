"""
Keyword search strategy using BM25 algorithm.

Industry standard: Sparse retrieval
- TF-IDF based keyword matching
- BM25 scoring algorithm
- Fast exact-match retrieval

Uses rank-bm25 library for efficient BM25 implementation.
"""

from typing import List, Dict, Any, Optional
import logging
import pickle
from pathlib import Path

from rank_bm25 import BM25Okapi
import numpy as np

from src.retrieval.search.base import BaseSearchStrategy, SearchResult

logger = logging.getLogger(__name__)


class KeywordSearchStrategy(BaseSearchStrategy):
    """
    Keyword search using BM25 algorithm.
    
    BM25 (Best Matching 25) is a ranking function used for:
    - Keyword-based search
    - Exact term matching
    - Document relevance scoring
    
    Works independently of vector store - uses separate BM25 index.
    """
    
    def __init__(self, *args, index_path: Optional[str] = None, **kwargs):
        super().__init__(*args, **kwargs)
        
        self.index_path = index_path or ".cache/bm25_index"
        self.bm25_index = None
        self.documents = []
        self.doc_ids = []
        
        # Load index if exists
        self._load_index()
    
    def search(
        self,
        query: str,
        top_k: Optional[int] = None,
        filters: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> List[SearchResult]:
        """
        Execute BM25 keyword search.
        
        Args:
            query: Search query
            top_k: Number of results to return
            filters: Metadata filters
            **kwargs: Additional parameters
            
        Returns:
            List of search results sorted by BM25 score
        """
        top_k = top_k or self.config.top_k
        
        logger.info(f"BM25 search: query='{query[:50]}...', top_k={top_k}")
        
        if not self.bm25_index:
            logger.warning("BM25 index not loaded, building from vector store...")
            self._build_index_from_vector_store()
        
        if not self.bm25_index:
            logger.error("BM25 index unavailable")
            return []
        
        try:
            # Tokenize query
            tokenized_query = query.lower().split()
            
            # Get BM25 scores
            scores = self.bm25_index.get_scores(tokenized_query)
            
            # Get top-k indices
            top_indices = np.argsort(scores)[::-1][:top_k * 2]  # Get more for filtering
            
            # Convert to SearchResult
            search_results = []
            for idx in top_indices:
                if scores[idx] > 0:  # Only include non-zero scores
                    doc = self.documents[idx]
                    
                    # Apply filters if specified
                    if filters and not self._matches_filters(doc.get('metadata', {}), filters):
                        continue
                    
                    search_results.append(SearchResult(
                        id=self.doc_ids[idx],
                        content=doc.get('content', ''),
                        metadata=doc.get('metadata', {}),
                        score=float(scores[idx]),
                        strategy="keyword"
                    ))
            
            logger.info(f"BM25 search complete: found={len(search_results)}")
            
            return search_results[:top_k]
            
        except Exception as e:
            logger.error(f"BM25 search failed: {e}", exc_info=True)
            return []
    
    def get_strategy_name(self) -> str:
        return "keyword"
    
    def _build_index_from_vector_store(self):
        """Build BM25 index from vector store documents."""
        try:
            logger.info("Building BM25 index from vector store...")
            
            # Get all documents from vector store
            all_docs = self.vector_store.collection.get(
                include=['documents', 'metadatas']
            )
            
            if not all_docs or not all_docs.get('documents'):
                logger.warning("No documents found in vector store")
                return
            
            # Prepare documents for BM25
            self.documents = []
            self.doc_ids = all_docs['ids']
            
            tokenized_corpus = []
            for i, doc_text in enumerate(all_docs['documents']):
                self.documents.append({
                    'content': doc_text,
                    'metadata': all_docs['metadatas'][i] if all_docs.get('metadatas') else {}
                })
                
                # Tokenize for BM25
                tokenized_corpus.append(doc_text.lower().split())
            
            # Build BM25 index
            self.bm25_index = BM25Okapi(tokenized_corpus)
            
            logger.info(f"BM25 index built: {len(self.documents)} documents")
            
            # Save index
            self._save_index()
            
        except Exception as e:
            logger.error(f"Failed to build BM25 index: {e}", exc_info=True)
    
    def _load_index(self):
        """Load BM25 index from disk."""
        index_file = Path(self.index_path) / "bm25_index.pkl"
        
        if not index_file.exists():
            logger.debug("BM25 index file not found")
            return
        
        try:
            with open(index_file, 'rb') as f:
                data = pickle.load(f)
                self.bm25_index = data['index']
                self.documents = data['documents']
                self.doc_ids = data['doc_ids']
            
            logger.info(f"BM25 index loaded: {len(self.documents)} documents")
            
        except Exception as e:
            logger.error(f"Failed to load BM25 index: {e}")
    
    def _save_index(self):
        """Save BM25 index to disk."""
        index_file = Path(self.index_path)
        index_file.mkdir(parents=True, exist_ok=True)
        
        try:
            with open(index_file / "bm25_index.pkl", 'wb') as f:
                pickle.dump({
                    'index': self.bm25_index,
                    'documents': self.documents,
                    'doc_ids': self.doc_ids
                }, f)
            
            logger.info("BM25 index saved")
            
        except Exception as e:
            logger.error(f"Failed to save BM25 index: {e}")
    
    def _matches_filters(self, metadata: Dict, filters: Dict) -> bool:
        """Check if metadata matches filters."""
        for key, value in filters.items():
            if metadata.get(key) != value:
                return False
        return True
    
    def rebuild_index(self):
        """Force rebuild of BM25 index."""
        logger.info("Forcing BM25 index rebuild...")
        self._build_index_from_vector_store()
