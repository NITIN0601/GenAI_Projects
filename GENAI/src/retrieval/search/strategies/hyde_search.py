"""
HyDE (Hypothetical Document Embeddings) search strategy.

Industry standard: Advanced RAG technique
- Generate hypothetical answer using LLM
- Embed hypothetical answer
- Search with hypothetical embedding
- Often better than direct query embedding

Reference: https://arxiv.org/abs/2212.10496
Paper: "Precise Zero-Shot Dense Retrieval without Relevance Labels"
"""

from typing import List, Dict, Any, Optional
import logging

from src.retrieval.search.base import BaseSearchStrategy, SearchResult
from src.prompts.search_strategies import HYDE_PROMPT

logger = logging.getLogger(__name__)


class HyDESearchStrategy(BaseSearchStrategy):
    """
    HyDE (Hypothetical Document Embeddings) search strategy.
    
    How it works:
    1. Use LLM to generate hypothetical answer to query
    2. Embed the hypothetical answer (not the query)
    3. Search using hypothetical answer embedding
    4. Return most similar actual documents
    
    Why it works:
    - Hypothetical answers are closer to actual documents than queries
    - Bridges vocabulary gap between questions and answers
    - Better semantic matching for factual queries
    
    Example:
        Query: "What was revenue in Q1?"
        Hypothetical: "The company reported revenue of $X million in Q1 2025..."
        → This matches actual financial tables better than the query
    
    NOTE: Requires LLM for generating hypothetical documents.
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        if not self.embedding_manager:
            raise ValueError("HyDE requires embedding_manager")
        
        # LLM is optional - will use fallback if not available
        if not self.llm_manager:
            logger.warning(
                "HyDE works best with LLM. "
                "Without LLM, will fall back to vector search."
            )
        
        self.prompt_template = (
            self.config.hyde_prompt_template or
            HYDE_PROMPT.template
        )
    
    def search(
        self,
        query: str,
        top_k: Optional[int] = None,
        filters: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> List[SearchResult]:
        """
        Execute HyDE search.
        
        Args:
            query: Search query
            top_k: Number of results to return
            filters: Metadata filters
            **kwargs: Additional parameters
            
        Returns:
            List of search results
        """
        top_k = top_k or self.config.top_k
        filters = filters or self.config.filters
        
        logger.info(f"HyDE search: query='{query[:50]}...', top_k={top_k}")
        
        try:
            # Step 1: Generate hypothetical document
            hypothetical_doc = self._generate_hypothetical_document(query)
            
            if not hypothetical_doc:
                # Fallback to regular vector search
                logger.warning("HyDE generation failed, falling back to vector search")
                return self._fallback_vector_search(query, top_k, filters)
            
            logger.debug(f"Generated hypothetical doc: {hypothetical_doc[:100]}...")
            
            # Step 2: Embed hypothetical document
            hyde_embedding = self.embedding_manager.generate_embedding(
                hypothetical_doc
            )
            
            # Step 3: Search using hypothetical embedding
            # Note: We search with the embedding directly, not the text
            raw_results = self.vector_store.search(
                query=hypothetical_doc,  # Some stores need text
                top_k=top_k,
                filters=filters
            )
            
            # Step 4: Convert to SearchResult format
            search_results = self._convert_to_search_results(
                raw_results,
                strategy_name="hyde"
            )
            
            # Add hypothetical doc to metadata for debugging
            for result in search_results:
                result.metadata['hypothetical_doc'] = hypothetical_doc[:200]
            
            logger.info(f"HyDE search complete: found={len(search_results)}")
            
            return search_results[:top_k]
            
        except Exception as e:
            logger.error(f"HyDE search failed: {e}", exc_info=True)
            return self._fallback_vector_search(query, top_k, filters)
    
    def _generate_hypothetical_document(self, query: str) -> Optional[str]:
        """
        Generate hypothetical document using LLM.
        
        NOTE: LLM call is COMMENTED OUT by default.
        Uncomment to enable LLM-based HyDE search.
        """
        if not self.llm_manager:
            logger.debug("No LLM manager available for HyDE")
            return None
        
        try:
            # Format prompt
            prompt = self.prompt_template.format(query=query)
            
            # ============================================================
            # LLM CALL - COMMENTED OUT
            # Uncomment the following lines to enable LLM-based HyDE
            # ============================================================
            
            # hypothetical_doc = self.llm_manager.generate(
            #     prompt=prompt,
            #     max_tokens=self.config.hyde_max_tokens,
            #     temperature=self.config.hyde_temperature
            # )
            # return hypothetical_doc.strip()
            
            # ============================================================
            # PLACEHOLDER - Remove when LLM is enabled
            # ============================================================
            logger.warning("\n" + "="*60)
            logger.warning("⚠️  UNCOMMENT TO RUN LLM-BASED HYDE SEARCH")
            logger.warning("="*60)
            logger.warning(f"Prompt would be:\n{prompt[:200]}...")
            logger.warning("="*60 + "\n")
            
            # Return None to trigger fallback
            return None
            
        except Exception as e:
            logger.error(f"Failed to generate hypothetical document: {e}")
            return None
    
    def _fallback_vector_search(
        self,
        query: str,
        top_k: int,
        filters: Optional[Dict[str, Any]]
    ) -> List[SearchResult]:
        """Fallback to regular vector search if HyDE fails."""
        logger.info("Using fallback vector search")
        
        query_embedding = self.embedding_manager.generate_embedding(query)
        
        raw_results = self.vector_store.search(
            query=query,
            top_k=top_k,
            filters=filters
        )
        
        return self._convert_to_search_results(
            raw_results,
            strategy_name="hyde_fallback"
        )
    
    def get_strategy_name(self) -> str:
        return "hyde"
    
    def validate_config(self) -> bool:
        """Validate HyDE configuration."""
        if not super().validate_config():
            return False
        
        if not self.embedding_manager:
            logger.error("HyDE requires embedding_manager")
            return False
        
        # LLM is optional but recommended
        if not self.llm_manager:
            logger.warning("HyDE recommended to use with LLM")
        
        return True
