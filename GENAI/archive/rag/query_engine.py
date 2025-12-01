"""Main RAG query engine."""

from typing import Optional, Dict, Any
from rich.console import Console
from rich.markdown import Markdown

from models.schemas import RAGQuery, RAGResponse
from rag.retriever import get_retriever
from rag.llm_manager import get_llm_manager
from cache.redis_cache import get_redis_cache
from config.settings import settings


console = Console()


class QueryEngine:
    """
    Main RAG pipeline that orchestrates:
    1. Query parsing
    2. Retrieval from vector store
    3. Context building
    4. LLM generation
    5. Response formatting with citations
    """
    
    def __init__(
        self,
        retriever=None,
        llm_manager=None,
        cache=None
    ):
        """
        Initialize query engine.
        
        Args:
            retriever: Retriever instance
            llm_manager: LLM manager instance
            cache: Redis cache instance
        """
        self.retriever = retriever or get_retriever()
        self.llm_manager = llm_manager or get_llm_manager()
        self.cache = cache or get_redis_cache()
        
        console.print("[green]✓[/green] Query engine initialized")
    
    def query(
        self,
        query: str,
        filters: Optional[Dict[str, Any]] = None,
        top_k: int = None,
        use_cache: bool = True
    ) -> RAGResponse:
        """
        Execute RAG query.
        
        Args:
            query: User question
            filters: Metadata filters
            top_k: Number of chunks to retrieve
            use_cache: Whether to use cache
            
        Returns:
            RAGResponse with answer and sources
        """
        top_k = top_k or settings.TOP_K
        
        # Step 1: Parse query to extract implicit filters
        if filters is None:
            filters = self.retriever.parse_query_filters(query)
            if filters:
                console.print(f"[cyan]Detected filters:[/cyan] {filters}")
        
        # Step 2: Check cache
        context_key = f"{query}_{filters}_{top_k}"
        if use_cache:
            cached_response = self.cache.get_llm_response(query, context_key)
            if cached_response:
                console.print("[yellow]Using cached response[/yellow]")
                # Parse cached response (simplified)
                return RAGResponse(
                    answer=cached_response,
                    sources=[],
                    confidence=1.0,
                    retrieved_chunks=0
                )
        
        # Step 3: Retrieve relevant chunks
        console.print(f"[cyan]Retrieving relevant chunks...[/cyan]")
        retrieved_chunks = self.retriever.retrieve(
            query=query,
            top_k=top_k,
            filters=filters
        )
        
        if not retrieved_chunks:
            return RAGResponse(
                answer="I couldn't find any relevant information in the financial documents to answer your question.",
                sources=[],
                confidence=0.0,
                retrieved_chunks=0
            )
        
        console.print(f"[green]Retrieved {len(retrieved_chunks)} chunks[/green]")
        
        # Step 4: Build context
        context = self.retriever.build_context(retrieved_chunks)
        
        # Step 5: Generate answer with LLM
        console.print("[cyan]Generating answer...[/cyan]")
        answer = self.llm_manager.generate_with_context(
            query=query,
            context=context
        )
        
        # Step 6: Extract sources
        sources = self.retriever.extract_sources(retrieved_chunks)
        
        # Step 7: Calculate confidence (based on similarity scores)
        avg_similarity = sum(
            chunk.get('similarity', 0.5) for chunk in retrieved_chunks
        ) / len(retrieved_chunks)
        
        # Step 8: Cache response
        if use_cache:
            self.cache.set_llm_response(query, context_key, answer)
        
        # Step 9: Create response
        response = RAGResponse(
            answer=answer,
            sources=sources,
            confidence=avg_similarity,
            retrieved_chunks=len(retrieved_chunks)
        )
        
        return response
    
    def format_response(self, response: RAGResponse) -> str:
        """
        Format response for display.
        
        Args:
            response: RAG response
            
        Returns:
            Formatted string
        """
        output = []
        
        # Answer
        output.append("## Answer\n")
        output.append(response.answer)
        output.append("\n")
        
        # Sources
        if response.sources:
            output.append("\n## Sources\n")
            for i, source in enumerate(response.sources, 1):
                source_text = f"{i}. **{source.table_title}**"
                source_text += f" (Page {source.page_no}, {source.source_doc}"
                if source.quarter:
                    source_text += f", {source.quarter} {source.year}"
                else:
                    source_text += f", {source.year}"
                source_text += ")"
                output.append(source_text)
        
        # Metadata
        output.append(f"\n---\n*Retrieved {response.retrieved_chunks} chunks | Confidence: {response.confidence:.2%}*")
        
        return "\n".join(output)
    
    def display_response(self, response: RAGResponse):
        """
        Display response with rich formatting.
        
        Args:
            response: RAG response
        """
        formatted = self.format_response(response)
        md = Markdown(formatted)
        console.print(md)
    
    def interactive_query(self):
        """Start interactive query session."""
        console.print("\n[bold green]Financial RAG System - Interactive Mode[/bold green]")
        console.print("Ask questions about financial tables. Type 'exit' to quit.\n")
        
        while True:
            try:
                query = console.input("[bold cyan]Your question:[/bold cyan] ")
                
                if query.lower() in ['exit', 'quit', 'q']:
                    console.print("[yellow]Goodbye![/yellow]")
                    break
                
                if not query.strip():
                    continue
                
                # Execute query
                response = self.query(query)
                
                # Display response
                console.print()
                self.display_response(response)
                console.print()
                
            except KeyboardInterrupt:
                console.print("\n[yellow]Interrupted. Goodbye![/yellow]")
                break
            except Exception as e:
                console.print(f"[red]Error: {e}[/red]")


# Global query engine instance
_query_engine: Optional[QueryEngine] = None


def get_query_engine() -> QueryEngine:
    """Get or create global query engine instance."""
    global _query_engine
    if _query_engine is None:
        _query_engine = QueryEngine()
    return _query_engine
