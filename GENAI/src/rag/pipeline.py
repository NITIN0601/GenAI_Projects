"""Main RAG query engine using LangChain LCEL."""

from typing import Optional, Dict, Any, List
import logging
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough, RunnableParallel

from src.models.schemas import RAGResponse, TableMetadata
from src.retrieval.retriever import get_retriever
from src.infrastructure.llm.manager import get_llm_manager
from src.infrastructure.embeddings.manager import get_embedding_manager
from src.cache.backends.redis_cache import get_redis_cache
from src.prompts.few_shot import get_few_shot_manager
from config.settings import settings
from src.prompts import FINANCIAL_CHAT_PROMPT, COT_PROMPT, REACT_PROMPT

logger = logging.getLogger(__name__)


class QueryEngine:
    """
    Main RAG pipeline using LangChain LCEL.
    
    Orchestrates:
    1. Retrieval (using LangChain Retriever)
    2. Prompting (using LangChain Templates)
    3. Generation (using LangChain ChatModel)
    """
    
    def __init__(
        self,
        retriever=None,
        llm_manager=None,
        cache=None,
        prompt_strategy: str = "standard"
    ):
        """
        Initialize query engine.
        
        Args:
            retriever: Retriever instance
            llm_manager: LLM manager instance
            cache: Cache instance
            prompt_strategy: Prompt strategy ("standard", "few_shot", "cot", "react")
        """
        self.retriever = retriever or get_retriever()
        self.llm_manager = llm_manager or get_llm_manager()
        self.cache = cache or get_redis_cache()
        self.prompt_strategy = prompt_strategy
        
        # Store last retrieved chunks for export
        self._last_retrieved_chunks = []
        
        # Get LangChain components
        self.llm = self.llm_manager.get_langchain_model()
        
        # Select prompt based on strategy
        self.prompt = self._get_prompt_for_strategy(prompt_strategy)
        
        # Build LCEL Chain
        # Context is retrieved using the retriever
        # Question is passed through
        self.chain = (
            RunnableParallel(
                {"context": self._get_retriever_runnable, "question": RunnablePassthrough()}
            )
            | self.prompt
            | self.llm
            | StrOutputParser()
        )
        
        logger.info(f"LangChain Query Engine initialized (mode: {prompt_strategy})")
    
    def _get_prompt_for_strategy(self, strategy: str):
        """Get prompt template based on strategy."""
        if strategy == "few_shot":
            # Get embedding function for semantic similarity
            embedding_manager = get_embedding_manager()
            few_shot_manager = get_few_shot_manager(embedding_function=embedding_manager)
            
            return few_shot_manager.get_few_shot_prompt()
        
        elif strategy == "cot":
            return COT_PROMPT
        
        elif strategy == "react":
            return REACT_PROMPT
        
        else:  # "standard"
            return FINANCIAL_CHAT_PROMPT

    
    def _get_retriever_runnable(self, query: str):
        """Helper to use retriever in LCEL."""
        # This allows us to pass dynamic config/filters if needed
        # For now, just return relevant documents
        # Note: self.retriever needs to be a LangChain retriever
        # If it's our custom Orchestrator, we need to wrap it or use it directly
        if hasattr(self.retriever, 'get_relevant_documents'):
            # LangChain Retriever (including our SearchStrategy)
            docs = self.retriever.get_relevant_documents(query)
            # Note: docs are LangChain Documents, not SearchResults
            self._last_retrieved_chunks = docs  # Store for export
            return "\n\n".join([d.page_content for d in docs])
        else:
            # Fallback for legacy retriever
            # Note: Legacy retriever uses 'retrieve' method
            results = self.retriever.retrieve(query)
            # Store SearchResult objects
            self._last_retrieved_chunks = results
            # Handle both dict results and object results if any
            return "\n\n".join([r.content if hasattr(r, 'content') else r.get('content', '') for r in results])

    def query(
        self,
        query: str,
        filters: Optional[Dict[str, Any]] = None,
        top_k: int = None,
        use_cache: bool = True
    ) -> RAGResponse:
        """Execute RAG query using LangChain."""
        top_k = top_k or settings.TOP_K
        
        # Check cache
        context_key = f"{query}_{filters}_{top_k}"
        if use_cache and self.cache:
            cached_response = self.cache.get_llm_response(query, context_key)
            if cached_response:
                logger.info("Using cached response")
                return RAGResponse(
                    answer=cached_response,
                    sources=[],
                    confidence=1.0,
                    retrieved_chunks=0,
                    from_cache=True
                )
        
        logger.info("Executing LangChain pipeline...")
        
        try:
            # Execute chain
            response_text = self.chain.invoke(query)
            
            # Extract sources from retrieved chunks
            sources = self._extract_sources()
            
            # Save to cache
            if use_cache and self.cache:
                self.cache.set_llm_response(query, response_text, context_key)
            
            # Run evaluation if enabled
            evaluation_result = None
            confidence = 0.8  # Default confidence
            
            if settings.EVALUATION_ENABLED and settings.EVALUATION_AUTO_RUN:
                evaluation_result, confidence = self._run_evaluation(query, response_text)
            
            return RAGResponse(
                answer=response_text,
                sources=sources,
                confidence=confidence,
                retrieved_chunks=len(self._last_retrieved_chunks),
                evaluation=evaluation_result
            )
            
        except Exception as e:
            logger.error(f"Pipeline failed: {e}")
            return RAGResponse(
                answer=f"I encountered an error: {str(e)}",
                sources=[],
                confidence=0.0,
                retrieved_chunks=0
            )
    
    def _extract_sources(self) -> List[TableMetadata]:
        """Extract source metadata from last retrieved chunks."""
        sources = []
        seen_ids = set()  # Deduplicate sources
        
        for chunk in self._last_retrieved_chunks:
            try:
                # Handle LangChain Document objects
                if hasattr(chunk, 'metadata'):
                    meta = chunk.metadata
                else:
                    meta = chunk.get('metadata', {}) if isinstance(chunk, dict) else {}
                
                # If meta is already a TableMetadata object, use it directly
                if isinstance(meta, TableMetadata):
                    source_id = f"{meta.source_doc}_{meta.page_no}_{meta.table_title}"
                    if source_id not in seen_ids:
                        seen_ids.add(source_id)
                        sources.append(meta)
                    continue
                
                # If meta is a dict, build TableMetadata
                if isinstance(meta, dict):
                    # Create unique identifier for deduplication
                    source_id = f"{meta.get('source_doc', '')}_{meta.get('page_no', '')}_{meta.get('table_title', '')}"
                    
                    if source_id in seen_ids:
                        continue
                    seen_ids.add(source_id)
                    
                    # Build TableMetadata for source citation
                    source = TableMetadata(
                        table_id=meta.get('table_id', meta.get('chunk_reference_id', source_id)),
                        source_doc=meta.get('source_doc', 'unknown'),
                        page_no=int(meta.get('page_no', 0)),
                        table_title=meta.get('table_title', 'Unknown'),
                        year=int(meta.get('year', 0)) if meta.get('year') else None,
                        quarter=meta.get('quarter'),
                        report_type=meta.get('report_type', 'unknown'),
                        chunk_reference_id=meta.get('chunk_reference_id')
                    )
                    sources.append(source)
                
            except Exception as e:
                logger.debug(f"Could not extract source from chunk: {e}")
                continue
        
        return sources
    
    def _run_evaluation(self, query: str, answer: str) -> tuple:
        """Run evaluation on the response (only called when EVALUATION_AUTO_RUN=True)."""
        try:
            from src.evaluation import get_evaluation_manager
            
            # Get contexts from last retrieval
            contexts = []
            for doc in self._last_retrieved_chunks:
                if hasattr(doc, 'page_content'):
                    contexts.append(doc.page_content)
                elif hasattr(doc, 'content'):
                    contexts.append(doc.content)
            
            if not contexts:
                logger.debug("No contexts available for evaluation")
                return None, 0.8
            
            # Run evaluation
            manager = get_evaluation_manager()
            scores = manager.evaluate(query=query, answer=answer, contexts=contexts)
            
            if settings.EVALUATION_LOG_SCORES:
                logger.info(f"Evaluation scores: {scores.overall_score:.2f}")
            
            return scores.to_dict(), scores.overall_score
            
        except Exception as e:
            logger.warning(f"Evaluation failed: {e}")
            return None, 0.8

    def get_last_retrieved_chunks(self):
        """
        Get chunks from last query execution.
        
        Returns:
            List of retrieved chunks (SearchResult or LangChain Document objects)
        """
        return self._last_retrieved_chunks


# Global instance
_query_engine: Optional[QueryEngine] = None

def get_query_engine() -> QueryEngine:
    """Get global query engine."""
    global _query_engine
    if _query_engine is None:
        _query_engine = QueryEngine()
    return _query_engine
