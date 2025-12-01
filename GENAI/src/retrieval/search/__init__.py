"""
Search package - production-grade search strategies.

Main components:
- SearchOrchestrator: Main entry point for search operations
- SearchStrategy: Enum of available strategies
- SearchConfig: Configuration for search
- SearchResult: Search result data class

Available strategies:
- VECTOR: Semantic similarity search
- KEYWORD: BM25 keyword search
- HYBRID: Vector + Keyword fusion (RECOMMENDED)
- HYDE: Hypothetical Document Embeddings
- MULTI_QUERY: Query expansion

Usage:
    from src.retrieval.search import get_search_orchestrator, SearchStrategy
    
    orchestrator = get_search_orchestrator()
    results = orchestrator.search(
        query="What was revenue in Q1?",
        strategy=SearchStrategy.HYBRID
    )
"""

from src.retrieval.search.base import (
    SearchStrategy,
    SearchConfig,
    SearchResult,
    BaseSearchStrategy
)
from src.retrieval.search.factory import SearchStrategyFactory, get_search_factory
from src.retrieval.search.orchestrator import SearchOrchestrator, get_search_orchestrator

__all__ = [
    # Enums and data classes
    "SearchStrategy",
    "SearchConfig",
    "SearchResult",
    
    # Base class
    "BaseSearchStrategy",
    
    # Factory
    "SearchStrategyFactory",
    "get_search_factory",
    
    # Orchestrator (main interface)
    "SearchOrchestrator",
    "get_search_orchestrator",
]

