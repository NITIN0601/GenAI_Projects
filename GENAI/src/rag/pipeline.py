"""
Main RAG Query Engine using LangChain LCEL.

Provides thread-safe singleton access to the RAG pipeline with support for:
- Multiple prompt strategies (standard, few_shot, cot, react)
- Caching integration
- Automatic evaluation
- Source extraction

Example:
    >>> from src.rag import get_query_engine
    >>> 
    >>> engine = get_query_engine()
    >>> response = engine.query("What was the revenue in Q1?")
    >>> print(response.answer)
"""

from typing import Optional, Dict, Any, List, TYPE_CHECKING

from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough, RunnableParallel

from config.settings import settings
from src.core.singleton import ThreadSafeSingleton
from src.domain import RAGResponse, TableMetadata
from src.prompts import FINANCIAL_CHAT_PROMPT, COT_PROMPT, REACT_PROMPT
from src.utils import get_logger

logger = get_logger(__name__)

if TYPE_CHECKING:
    from src.retrieval.retriever import Retriever
    from src.infrastructure.llm.manager import LLMManager


class QueryEngine(metaclass=ThreadSafeSingleton):
    """
    Main RAG pipeline using LangChain LCEL.
    
    Thread-safe singleton manager for RAG query processing.
    
    Orchestrates:
    1. Retrieval (using LangChain Retriever)
    2. Prompting (using LangChain Templates)
    3. Generation (using LangChain ChatModel)
    
    Attributes:
        retriever: Document retriever instance
        llm_manager: LLM manager instance
        prompt_strategy: Current prompt strategy
    """
    
    def __init__(
        self,
        retriever: Optional["Retriever"] = None,
        llm_manager: Optional["LLMManager"] = None,
        cache: Any = None,
        prompt_strategy: str = "standard"
    ):
        """
        Initialize query engine.
        
        Args:
            retriever: Retriever instance (auto-created if None)
            llm_manager: LLM manager instance (auto-created if None)
            cache: Cache instance (auto-created if None)
            prompt_strategy: Prompt strategy ("standard", "few_shot", "cot", "react")
        """
        # Lazy initialization
        self._retriever = retriever
        self._llm_manager = llm_manager
        self._cache = cache
        self.prompt_strategy = prompt_strategy
        
        # Store last retrieved chunks for export
        self._last_retrieved_chunks: List[Any] = []
        
        # Initialize components
        self._initialize_chain()
        
        logger.info(f"QueryEngine initialized (mode: {prompt_strategy})")
    
    def _initialize_chain(self) -> None:
        """Initialize the LangChain LCEL chain."""
        # Get LangChain components
        self.llm = self.llm_manager.get_langchain_model()
        
        # Select prompt based on strategy
        self.prompt = self._get_prompt_for_strategy(self.prompt_strategy)
        
        # Build LCEL Chain
        self.chain = (
            RunnableParallel(
                {"context": self._get_retriever_runnable, "question": RunnablePassthrough()}
            )
            | self.prompt
            | self.llm
            | StrOutputParser()
        )
    
    @property
    def retriever(self) -> "Retriever":
        """Get retriever (lazy initialization)."""
        if self._retriever is None:
            from src.retrieval.retriever import get_retriever
            self._retriever = get_retriever()
        return self._retriever
    
    @property
    def llm_manager(self) -> "LLMManager":
        """Get LLM manager (lazy initialization)."""
        if self._llm_manager is None:
            from src.infrastructure.llm.manager import get_llm_manager
            self._llm_manager = get_llm_manager()
        return self._llm_manager
    
    @property
    def cache(self) -> Any:
        """Get cache (lazy initialization)."""
        if self._cache is None:
            from src.infrastructure.cache import get_redis_cache
            self._cache = get_redis_cache()
        return self._cache
    
    @property
    def name(self) -> str:
        """Provider name (implements BaseProvider protocol)."""
        return f"query-engine:{self.prompt_strategy}"
    
    def is_available(self) -> bool:
        """Check if engine is available (implements BaseProvider protocol)."""
        try:
            return self.llm_manager.is_available()
        except Exception:
            return False
    
    def health_check(self) -> Dict[str, Any]:
        """
        Perform health check (implements BaseProvider protocol).
        
        Returns:
            Dict with 'status' and optional details
        """
        try:
            available = self.is_available()
            return {
                "status": "ok" if available else "error",
                "prompt_strategy": self.prompt_strategy,
                "llm_available": self.llm_manager.is_available() if self._llm_manager else False,
            }
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
            }
    
    def _get_prompt_for_strategy(self, strategy: str):
        """Get prompt template based on strategy."""
        if strategy == "few_shot":
            from src.infrastructure.embeddings.manager import get_embedding_manager
            from src.prompts.few_shot import get_few_shot_manager
            
            embedding_manager = get_embedding_manager()
            few_shot_manager = get_few_shot_manager(embedding_function=embedding_manager)
            return few_shot_manager.get_few_shot_prompt()
        
        elif strategy == "cot":
            return COT_PROMPT
        
        elif strategy == "react":
            return REACT_PROMPT
        
        else:  # "standard"
            return FINANCIAL_CHAT_PROMPT

    def _get_retriever_runnable(self, query: str) -> str:
        """Helper to use retriever in LCEL."""
        if hasattr(self.retriever, 'get_relevant_documents'):
            # LangChain Retriever
            docs = self.retriever.get_relevant_documents(query)
            self._last_retrieved_chunks = docs
            return "\n\n".join([d.page_content for d in docs])
        else:
            # Legacy retriever
            results = self.retriever.retrieve(query)
            self._last_retrieved_chunks = results
            return "\n\n".join([
                r.content if hasattr(r, 'content') else r.get('content', '') 
                for r in results
            ])

    def query(
        self,
        query: str,
        filters: Optional[Dict[str, Any]] = None,
        top_k: Optional[int] = None,
        use_cache: bool = True
    ) -> RAGResponse:
        """
        Execute RAG query using LangChain.
        
        Args:
            query: User query
            filters: Optional metadata filters
            top_k: Number of documents to retrieve
            use_cache: Whether to use cache
            
        Returns:
            RAGResponse with answer, sources, and metadata
        """
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
            confidence = 0.8
            
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
        seen_ids = set()
        
        for chunk in self._last_retrieved_chunks:
            try:
                # Handle LangChain Document objects
                if hasattr(chunk, 'metadata'):
                    meta = chunk.metadata
                else:
                    meta = chunk.get('metadata', {}) if isinstance(chunk, dict) else {}
                
                # If meta is already a TableMetadata object
                if isinstance(meta, TableMetadata):
                    source_id = f"{meta.source_doc}_{meta.page_no}_{meta.table_title}"
                    if source_id not in seen_ids:
                        seen_ids.add(source_id)
                        sources.append(meta)
                    continue
                
                # If meta is a dict, build TableMetadata
                if isinstance(meta, dict):
                    source_id = f"{meta.get('source_doc', '')}_{meta.get('page_no', '')}_{meta.get('table_title', '')}"
                    
                    if source_id in seen_ids:
                        continue
                    seen_ids.add(source_id)
                    
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
        """Run evaluation on the response."""
        try:
            from src.evaluation import get_evaluation_manager
            
            contexts = []
            for doc in self._last_retrieved_chunks:
                if hasattr(doc, 'page_content'):
                    contexts.append(doc.page_content)
                elif hasattr(doc, 'content'):
                    contexts.append(doc.content)
            
            if not contexts:
                logger.debug("No contexts available for evaluation")
                return None, 0.8
            
            manager = get_evaluation_manager()
            scores = manager.evaluate(query=query, answer=answer, contexts=contexts)
            
            if settings.EVALUATION_LOG_SCORES:
                logger.info(f"Evaluation scores: {scores.overall_score:.2f}")
            
            return scores.to_dict(), scores.overall_score
            
        except Exception as e:
            logger.warning(f"Evaluation failed: {e}")
            return None, 0.8

    def get_last_retrieved_chunks(self) -> List[Any]:
        """
        Get chunks from last query execution.
        
        Returns:
            List of retrieved chunks (SearchResult or LangChain Document objects)
        """
        return self._last_retrieved_chunks


def get_query_engine(
    retriever: Optional["Retriever"] = None,
    llm_manager: Optional["LLMManager"] = None,
    **kwargs
) -> QueryEngine:
    """
    Get or create global query engine instance.
    
    Thread-safe singleton accessor.
    
    Args:
        retriever: Retriever instance (only used on first call)
        llm_manager: LLM manager (only used on first call)
        **kwargs: Additional arguments
        
    Returns:
        QueryEngine singleton instance
    """
    return QueryEngine(
        retriever=retriever,
        llm_manager=llm_manager,
        **kwargs
    )


def reset_query_engine() -> None:
    """
    Reset the query engine singleton.
    
    Useful for testing or reconfiguration.
    """
    QueryEngine._reset_instance()
