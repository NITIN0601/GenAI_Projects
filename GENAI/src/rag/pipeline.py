"""Main RAG query engine using LangChain LCEL."""

from typing import Optional, Dict, Any
from rich.console import Console
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough, RunnableParallel

from src.models.schemas import RAGResponse
from src.retrieval.retriever import get_retriever
from src.llm.manager import get_llm_manager
from src.embeddings.manager import get_embedding_manager
from src.cache.backends.redis_cache import get_redis_cache
from src.rag.few_shot_examples import get_few_shot_manager
from config.settings import settings
from config.prompts import FINANCIAL_CHAT_PROMPT, COT_PROMPT, REACT_PROMPT

console = Console()


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
        
        console.print(f"[green][OK][/green] LangChain Query Engine initialized (mode: {prompt_strategy})")
    
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
            return "\n\n".join([d.page_content for d in docs])
        else:
            # Fallback for legacy retriever
            # Note: Legacy retriever uses 'retrieve' method
            results = self.retriever.retrieve(query)
            # Handle both dict results and object results if any
            return "\n\n".join([r.get('content', '') if isinstance(r, dict) else getattr(r, 'content', '') for r in results])

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
                console.print("[yellow]Using cached response[/yellow]")
                return RAGResponse(
                    answer=cached_response,
                    sources=[],
                    confidence=1.0,
                    retrieved_chunks=0
                )
        
        console.print(f"[cyan]Executing LangChain pipeline...[/cyan]")
        
        try:
            # Execute chain
            # We can pass filters/top_k if we update the retriever config before running
            # For now, we assume retriever is configured
            
            response_text = self.chain.invoke(query)
            
            # Save to cache
            if use_cache and self.cache:
                self.cache.set_llm_response(query, response_text, context_key)
            
            return RAGResponse(
                answer=response_text,
                sources=[], # We'd need to extract sources from retrieval step
                confidence=0.8,
                retrieved_chunks=0 # Placeholder
            )
            
        except Exception as e:
            console.print(f"[red]Pipeline failed: {e}[/red]")
            return RAGResponse(
                answer=f"I encountered an error: {str(e)}",
                sources=[],
                confidence=0.0,
                retrieved_chunks=0
            )


# Global instance
_query_engine: Optional[QueryEngine] = None

def get_query_engine() -> QueryEngine:
    """Get global query engine."""
    global _query_engine
    if _query_engine is None:
        _query_engine = QueryEngine()
    return _query_engine
