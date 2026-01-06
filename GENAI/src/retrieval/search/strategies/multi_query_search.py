"""
Multi-Query search strategy - query expansion using LLM.

Industry standard: Query expansion
- Generate multiple query variations
- Search with each variation
- Fuse results using RRF
- Improve recall and handle ambiguity

Reference: LangChain MultiQueryRetriever
"""

from typing import List, Dict, Any, Optional
import logging
from src.utils import get_logger

from src.retrieval.search.base import BaseSearchStrategy, SearchResult
from src.prompts.search_strategies import MULTI_QUERY_PROMPT

logger = get_logger(__name__)


class MultiQuerySearchStrategy(BaseSearchStrategy):
    """
    Multi-query search strategy using query expansion.
    
    How it works:
    1. Use LLM to generate multiple query variations
    2. Search with each variation independently
    3. Fuse results using Reciprocal Rank Fusion (RRF)
    4. Return deduplicated, ranked results
    
    Benefits:
    - Better recall (finds more relevant documents)
    - Handles query ambiguity
    - Finds related information
    - Robust to query phrasing
    
    Example:
        Query: "What was revenue?"
        Variations:
        - "What was the total revenue?"
        - "What were the company's sales?"
        - "How much money did the company make?"
        → Search with all, fuse results
    
    NOTE: Requires LLM for generating query variations.
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        if not self.embedding_manager:
            raise ValueError("Multi-query requires embedding_manager")
        
        # LLM is optional - will use fallback if not available
        if not self.llm_manager:
            logger.warning(
                "Multi-query works best with LLM. "
                "Without LLM, will fall back to vector search."
            )
    
    def search(
        self,
        query: str,
        top_k: Optional[int] = None,
        filters: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> List[SearchResult]:
        """
        Execute multi-query search.
        
        Args:
            query: Search query
            top_k: Number of results to return
            filters: Metadata filters
            **kwargs: Additional parameters
            
        Returns:
            List of fused search results
        """
        top_k = top_k or self.config.top_k
        filters = filters or self.config.filters
        num_queries = self.config.num_queries
        
        logger.info(
            f"Multi-query search: query='{query[:50]}...', "
            f"num_queries={num_queries}, top_k={top_k}"
        )
        
        try:
            # Step 1: Generate query variations
            queries = self._generate_query_variations(query, num_queries)
            
            if len(queries) == 1:
                # Fallback to single query
                logger.warning("Multi-query generation failed, using single query")
                return self._fallback_vector_search(query, top_k, filters)
            
            logger.info(f"Generated {len(queries)} query variations")
            
            # Step 2: Search with each query
            all_results = []
            for i, q in enumerate(queries):
                logger.debug(f"Searching with query {i+1}: {q[:50]}...")
                
                # Generate embedding
                embedding = self.embedding_manager.generate_embedding(q)
                
                # Search
                raw_results = self.vector_store.search(
                    query=q,
                    top_k=top_k * 2,  # Get more results for fusion
                    filters=filters
                )
                
                # Convert to SearchResult
                search_results = self._convert_to_search_results(
                    raw_results,
                    strategy_name="multi_query"
                )
                
                all_results.append(search_results)
            
            # Step 3: Fuse results using RRF
            fused_results = self._reciprocal_rank_fusion(all_results)
            
            logger.info(f"Multi-query search complete: fused={len(fused_results)}")
            
            return fused_results[:top_k]
            
        except Exception as e:
            logger.error(f"Multi-query search failed: {e}", exc_info=True)
            return self._fallback_vector_search(query, top_k, filters)
    
    def _generate_query_variations(
        self,
        query: str,
        num_queries: int
    ) -> List[str]:
        """
        Generate query variations using LLM.
        
        NOTE: LLM call is COMMENTED OUT by default.
        Uncomment to enable LLM-based multi-query search.
        """
        if not self.llm_manager:
            logger.debug("No LLM manager available for multi-query")
            return [query]  # Return original only
        
        try:
            # Format prompt
            prompt = MULTI_QUERY_PROMPT.template.format(
                query=query,
                num_queries=num_queries
            )
            
            # ============================================================
            # LLM CALL - COMMENTED OUT
            # Uncomment the following lines to enable LLM-based multi-query
            # ============================================================
            
            # response = self.llm_manager.generate(
            #     prompt=prompt,
            #     max_tokens=300,
            #     temperature=self.config.multi_query_temperature
            # )
            # 
            # # Parse response
            # queries = [query]  # Include original
            # lines = response.strip().split('\n')
            # 
            # for line in lines:
            #     line = line.strip()
            #     if line and line[0].isdigit():
            #         # Remove numbering (e.g., "1. " or "2. ")
            #         q = line.split('.', 1)[-1].strip()
            #         if q and q not in queries:
            #             queries.append(q)
            # 
            # return queries[:num_queries + 1]
            
            # ============================================================
            # PLACEHOLDER - Remove when LLM is enabled
            # ============================================================
            logger.warning("\n" + "="*60)
            logger.warning("UNCOMMENT TO RUN LLM-BASED MULTI-QUERY SEARCH")
            logger.warning("="*60)
            logger.warning(f"Prompt would be:\n{prompt[:200]}...")
            logger.warning("="*60 + "\n")
            
            # Return original query only (triggers fallback)
            return [query]
            
        except Exception as e:
            logger.error(f"Failed to generate query variations: {e}")
            return [query]
    
    def _reciprocal_rank_fusion(
        self,
        results_list: List[List[SearchResult]],
        k: int = 60
    ) -> List[SearchResult]:
        """
        Fuse multiple result lists using Reciprocal Rank Fusion (RRF).
        
        RRF formula: score(d) = Σ(1 / (k + rank(d)))
        
        Args:
            results_list: List of ranked result lists
            k: RRF constant (default: 60)
            
        Returns:
            Fused and re-ranked results
        """
        # Collect all unique documents with their RRF scores
        doc_scores = {}
        
        for results in results_list:
            for rank, result in enumerate(results, start=1):
                doc_id = result.id
                
                # RRF score contribution from this ranking
                rrf_score = 1.0 / (k + rank)
                
                if doc_id in doc_scores:
                    doc_scores[doc_id]['score'] += rrf_score
                else:
                    doc_scores[doc_id] = {
                        'result': result,
                        'score': rrf_score
                    }
        
        # Sort by RRF score
        sorted_docs = sorted(
            doc_scores.items(),
            key=lambda x: x[1]['score'],
            reverse=True
        )
        
        # Create fused results with updated scores
        fused_results = []
        for doc_id, data in sorted_docs:
            result = data['result']
            result.score = data['score']  # Update with RRF score
            fused_results.append(result)
        
        return fused_results
    
    def _fallback_vector_search(
        self,
        query: str,
        top_k: int,
        filters: Optional[Dict[str, Any]]
    ) -> List[SearchResult]:
        """Fallback to regular vector search if multi-query fails."""
        logger.info("Using fallback vector search")
        
        query_embedding = self.embedding_manager.generate_embedding(query)
        
        raw_results = self.vector_store.search(
            query=query,
            top_k=top_k,
            filters=filters
        )
        
        return self._convert_to_search_results(
            raw_results,
            strategy_name="multi_query_fallback"
        )
    
    def get_strategy_name(self) -> str:
        return "multi_query"
    
    def validate_config(self) -> bool:
        """Validate multi-query configuration."""
        if not super().validate_config():
            return False
        
        if not self.embedding_manager:
            logger.error("Multi-query requires embedding_manager")
            return False
        
        if self.config.num_queries < 1:
            logger.error("num_queries must be >= 1")
            return False
        
        # LLM is optional but recommended
        if not self.llm_manager:
            logger.warning("Multi-query recommended to use with LLM")
        
        return True
