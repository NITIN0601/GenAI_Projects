"""
Provider Registry Pattern for GENAI.

Provides a generic registry for registering and creating provider instances.
Eliminates duplicate if/elif chains across managers.

Example:
    >>> # Define providers
    >>> class OpenAIProvider:
    ...     def __init__(self, api_key):
    ...         self.api_key = api_key
    >>> 
    >>> class OllamaProvider:
    ...     def __init__(self, base_url="http://localhost:11434"):
    ...         self.base_url = base_url
    >>> 
    >>> # Create registry and register providers
    >>> llm_registry = ProviderRegistry("llm")
    >>> llm_registry.register("openai", OpenAIProvider)
    >>> llm_registry.register("ollama", OllamaProvider)
    >>> 
    >>> # Create provider instance
    >>> provider = llm_registry.create("ollama", base_url="http://localhost:11434")
"""

from typing import Any, Callable, Dict, List, Optional, Type, TypeVar, Generic
import logging

from src.utils import get_logger

logger = get_logger(__name__)

T = TypeVar('T')


class ProviderNotRegisteredError(Exception):
    """Raised when attempting to create an unregistered provider."""
    
    def __init__(self, provider_name: str, registry_name: str, available: List[str]):
        self.provider_name = provider_name
        self.registry_name = registry_name
        self.available = available
        super().__init__(
            f"Provider '{provider_name}' not registered in {registry_name} registry. "
            f"Available providers: {', '.join(available)}"
        )


class ProviderRegistry(Generic[T]):
    """
    Generic provider registry for managing provider factories.
    
    Features:
    - Register provider factories by name
    - Create provider instances with configuration
    - List available providers
    - Lazy loading support via factory callables
    
    Example:
        >>> registry = ProviderRegistry[LLMProvider]("llm")
        >>> registry.register("openai", OpenAIProvider, default_kwargs={"model": "gpt-4"})
        >>> provider = registry.create("openai", api_key="...")
    """
    
    def __init__(self, name: str):
        """
        Initialize the provider registry.
        
        Args:
            name: Registry name for error messages and logging
        """
        self.name = name
        self._providers: Dict[str, Type[T]] = {}
        self._factories: Dict[str, Callable[..., T]] = {}
        self._default_kwargs: Dict[str, Dict[str, Any]] = {}
        self._aliases: Dict[str, str] = {}
    
    def register(
        self,
        name: str,
        provider: Type[T] = None,
        *,
        factory: Callable[..., T] = None,
        aliases: List[str] = None,
        default_kwargs: Dict[str, Any] = None,
    ) -> None:
        """
        Register a provider class or factory.
        
        Args:
            name: Provider name (e.g., "openai", "ollama")
            provider: Provider class (optional if factory provided)
            factory: Factory callable (optional if provider provided)
            aliases: Alternative names for this provider
            default_kwargs: Default keyword arguments for instantiation
            
        Raises:
            ValueError: If neither provider nor factory is provided
        """
        if provider is None and factory is None:
            raise ValueError("Must provide either 'provider' class or 'factory' callable")
        
        name_lower = name.lower()
        
        if provider is not None:
            self._providers[name_lower] = provider
        
        if factory is not None:
            self._factories[name_lower] = factory
        
        if default_kwargs:
            self._default_kwargs[name_lower] = default_kwargs
        
        # Register aliases
        if aliases:
            for alias in aliases:
                self._aliases[alias.lower()] = name_lower
        
        logger.debug(f"Registered {self.name} provider: {name}")
    
    def register_lazy(
        self,
        name: str,
        import_path: str,
        class_name: str,
        aliases: List[str] = None,
        default_kwargs: Dict[str, Any] = None,
    ) -> None:
        """
        Register a provider with lazy import.
        
        The provider class is not imported until first use.
        
        Args:
            name: Provider name
            import_path: Module path to import from
            class_name: Class name to import
            aliases: Alternative names
            default_kwargs: Default instantiation arguments
        """
        def lazy_factory(**kwargs):
            import importlib
            module = importlib.import_module(import_path)
            cls = getattr(module, class_name)
            return cls(**kwargs)
        
        self.register(
            name,
            factory=lazy_factory,
            aliases=aliases,
            default_kwargs=default_kwargs,
        )
    
    def create(self, name: str, **kwargs) -> T:
        """
        Create a provider instance.
        
        Args:
            name: Provider name or alias
            **kwargs: Provider constructor arguments
            
        Returns:
            Provider instance
            
        Raises:
            ProviderNotRegisteredError: If provider is not registered
        """
        name_lower = name.lower()
        
        # Resolve alias
        if name_lower in self._aliases:
            name_lower = self._aliases[name_lower]
        
        # Check if registered
        if name_lower not in self._providers and name_lower not in self._factories:
            raise ProviderNotRegisteredError(
                name,
                self.name,
                self.list_providers()
            )
        
        # Merge default kwargs with provided kwargs
        merged_kwargs = {**self._default_kwargs.get(name_lower, {}), **kwargs}
        
        # Create instance using factory or class
        if name_lower in self._factories:
            logger.debug(f"Creating {self.name} provider '{name}' via factory")
            return self._factories[name_lower](**merged_kwargs)
        else:
            logger.debug(f"Creating {self.name} provider '{name}' via class")
            return self._providers[name_lower](**merged_kwargs)
    
    def list_providers(self) -> List[str]:
        """
        List all registered provider names.
        
        Returns:
            List of provider names (not including aliases)
        """
        all_names = set(self._providers.keys()) | set(self._factories.keys())
        return sorted(all_names)
    
    def list_aliases(self) -> Dict[str, str]:
        """
        List all registered aliases.
        
        Returns:
            Dict mapping alias to provider name
        """
        return dict(self._aliases)
    
    def is_registered(self, name: str) -> bool:
        """
        Check if a provider is registered.
        
        Args:
            name: Provider name or alias
            
        Returns:
            True if registered, False otherwise
        """
        name_lower = name.lower()
        if name_lower in self._aliases:
            name_lower = self._aliases[name_lower]
        return name_lower in self._providers or name_lower in self._factories
    
    def unregister(self, name: str) -> bool:
        """
        Unregister a provider.
        
        Args:
            name: Provider name
            
        Returns:
            True if provider was removed, False if not found
        """
        name_lower = name.lower()
        removed = False
        
        if name_lower in self._providers:
            del self._providers[name_lower]
            removed = True
        
        if name_lower in self._factories:
            del self._factories[name_lower]
            removed = True
        
        if name_lower in self._default_kwargs:
            del self._default_kwargs[name_lower]
        
        # Remove aliases pointing to this provider
        self._aliases = {
            alias: target 
            for alias, target in self._aliases.items() 
            if target != name_lower
        }
        
        if removed:
            logger.debug(f"Unregistered {self.name} provider: {name}")
        
        return removed


# Pre-configured registries for common provider types
# These can be imported and extended by each manager module

def create_llm_registry() -> ProviderRegistry:
    """Create a pre-configured LLM provider registry.
    
    Model defaults are loaded from config/settings.py for consistency.
    """
    from config.settings import settings
    
    registry = ProviderRegistry("llm")
    
    # Register Ollama (default local option)
    # Model default loaded from settings for consistency
    registry.register_lazy(
        "ollama",
        "src.infrastructure.llm.providers.base",
        "OllamaLLMProvider",
        aliases=["local"],
        default_kwargs={"model": settings.OLLAMA_MODEL}
    )
    
    # Register OpenAI
    # Model default loaded from settings for consistency
    registry.register_lazy(
        "openai",
        "src.infrastructure.llm.providers.base",
        "OpenAILLMProvider",
        aliases=["gpt"],
        default_kwargs={"model": settings.OPENAI_MODEL}
    )
    
    return registry


def create_vectordb_registry() -> ProviderRegistry:
    """Create a pre-configured VectorDB provider registry."""
    registry = ProviderRegistry("vectordb")
    
    # Register ChromaDB
    registry.register_lazy(
        "chromadb",
        "src.infrastructure.vectordb.stores.chromadb_store",
        "VectorStore",
        aliases=["chroma"]
    )
    
    # Register FAISS
    registry.register_lazy(
        "faiss",
        "src.infrastructure.vectordb.stores.faiss_store",
        "FAISSVectorStore",
    )
    
    # Register Redis
    registry.register_lazy(
        "redis",
        "src.infrastructure.vectordb.stores.redis_store",
        "RedisVectorStore",
    )
    
    return registry


def create_embedding_registry() -> ProviderRegistry:
    """Create a pre-configured embedding provider registry."""
    registry = ProviderRegistry("embedding")
    
    # Embedding providers are handled differently due to LangChain integration
    # This registry is mainly for reference
    
    return registry
