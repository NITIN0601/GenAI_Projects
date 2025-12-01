"""
Strategy Factory - creates search strategy instances.

Industry standard: Factory Pattern
- Centralized strategy creation
- Easy to extend with new strategies
- Configuration management
"""

from typing import Optional, Dict, Any, Type
import logging

from src.retrieval.search.base import (
    BaseSearchStrategy,
    SearchStrategy,
    SearchConfig
)

logger = logging.getLogger(__name__)


class SearchStrategyFactory:
    """
    Factory for creating search strategy instances.
    
    Usage:
        factory = SearchStrategyFactory()
        strategy = factory.create(
            SearchStrategy.HYBRID,
            vector_store=vs,
            embedding_manager=em
        )
        results = strategy.search("query")
    
    Extensible:
        factory.register_strategy("custom", CustomStrategy)
    """
    
    # Strategy registry (lazy loaded to avoid circular imports)
    _strategies: Dict[str, Type[BaseSearchStrategy]] = {}
    _initialized = False
    
    @classmethod
    def _initialize_strategies(cls):
        """Initialize strategy registry (lazy loading)."""
        if cls._initialized:
            return
        
        # Import strategies here to avoid circular imports
        from src.retrieval.search.strategies.vector_search import VectorSearchStrategy
        from src.retrieval.search.strategies.keyword_search import KeywordSearchStrategy
        from src.retrieval.search.strategies.hybrid_search import HybridSearchStrategy
        from src.retrieval.search.strategies.hyde_search import HyDESearchStrategy
        from src.retrieval.search.strategies.multi_query_search import MultiQuerySearchStrategy
        
        cls._strategies = {
            SearchStrategy.VECTOR: VectorSearchStrategy,
            SearchStrategy.KEYWORD: KeywordSearchStrategy,
            SearchStrategy.HYBRID: HybridSearchStrategy,
            SearchStrategy.HYDE: HyDESearchStrategy,
            SearchStrategy.MULTI_QUERY: MultiQuerySearchStrategy
        }
        
        cls._initialized = True
        logger.info(f"Initialized {len(cls._strategies)} search strategies")
    
    @classmethod
    def create(
        cls,
        strategy: SearchStrategy,
        vector_store,
        embedding_manager=None,
        llm_manager=None,
        config: Optional[SearchConfig] = None,
        **kwargs
    ) -> BaseSearchStrategy:
        """
        Create search strategy instance.
        
        Args:
            strategy: Strategy type (e.g., SearchStrategy.HYBRID)
            vector_store: Vector store instance
            embedding_manager: Embedding manager (required for most strategies)
            llm_manager: LLM manager (optional, for HyDE/Multi-Query)
            config: Search configuration
            **kwargs: Additional strategy-specific parameters
            
        Returns:
            Search strategy instance
            
        Raises:
            ValueError: If strategy is unknown or invalid
        """
        cls._initialize_strategies()
        
        if strategy not in cls._strategies:
            raise ValueError(
                f"Unknown strategy: {strategy}. "
                f"Available: {list(cls._strategies.keys())}"
            )
        
        strategy_class = cls._strategies[strategy]
        
        try:
            instance = strategy_class(
                vector_store=vector_store,
                embedding_manager=embedding_manager,
                llm_manager=llm_manager,
                config=config or SearchConfig(),
                **kwargs
            )
            
            logger.info(f"Created strategy: {strategy}")
            return instance
            
        except Exception as e:
            logger.error(f"Failed to create strategy {strategy}: {e}")
            raise
    
    @classmethod
    def register_strategy(
        cls,
        name: str,
        strategy_class: Type[BaseSearchStrategy]
    ):
        """
        Register custom search strategy.
        
        Allows users to add custom strategies:
        
        Example:
            class CustomStrategy(BaseSearchStrategy):
                def search(self, query, **kwargs):
                    # Custom logic
                    pass
                
                def get_strategy_name(self):
                    return "custom"
            
            SearchStrategyFactory.register_strategy(
                "custom",
                CustomStrategy
            )
            
            # Now can use it
            strategy = factory.create("custom", ...)
        
        Args:
            name: Strategy name
            strategy_class: Strategy class (must inherit from BaseSearchStrategy)
        """
        cls._initialize_strategies()
        
        if not issubclass(strategy_class, BaseSearchStrategy):
            raise ValueError(
                f"{strategy_class} must inherit from BaseSearchStrategy"
            )
        
        cls._strategies[name] = strategy_class
        logger.info(f"Registered custom strategy: {name}")
    
    @classmethod
    def get_available_strategies(cls) -> list:
        """Get list of available strategy names."""
        cls._initialize_strategies()
        return list(cls._strategies.keys())
    
    @classmethod
    def get_strategy_info(cls, strategy: SearchStrategy) -> Dict[str, Any]:
        """Get information about a strategy."""
        cls._initialize_strategies()
        
        if strategy not in cls._strategies:
            return {}
        
        strategy_class = cls._strategies[strategy]
        
        return {
            "name": strategy,
            "class": strategy_class.__name__,
            "module": strategy_class.__module__,
            "docstring": strategy_class.__doc__
        }


# Global factory instance
_factory: Optional[SearchStrategyFactory] = None


def get_search_factory() -> SearchStrategyFactory:
    """Get or create global search factory instance."""
    global _factory
    if _factory is None:
        _factory = SearchStrategyFactory()
    return _factory
