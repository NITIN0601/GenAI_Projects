"""
Embedding Manager - Unified embedding interface using LangChain.

Provides thread-safe singleton access to embedding providers with support for:
- Local HuggingFace (sentence-transformers, default)
- OpenAI (text-embedding-3-small, text-embedding-ada-002)
- Custom API (bearer token)

Dimension is auto-detected from actual model output.

Example:
    >>> from src.infrastructure.embeddings import get_embedding_manager
    >>> 
    >>> embeddings = get_embedding_manager()
    >>> vector = embeddings.embed_query("What is AI?")
    >>> print(f"Dimension: {len(vector)}")
"""

from typing import List, Optional, Dict, Any, TYPE_CHECKING

from langchain_core.embeddings import Embeddings

from config.settings import settings
from src.utils import get_logger

logger = get_logger(__name__)

# Thread-safe singleton state
_embedding_manager_instance: Optional["EmbeddingManager"] = None
_embedding_manager_lock = None

def _get_lock():
    """Get or create the singleton lock."""
    global _embedding_manager_lock
    if _embedding_manager_lock is None:
        import threading
        _embedding_manager_lock = threading.Lock()
    return _embedding_manager_lock


class EmbeddingManager:
    """
    Unified Embedding Manager implementing LangChain Embeddings interface.
    
    Thread-safe singleton manager for embedding providers.
    
    Wraps specific providers (HuggingFace, OpenAI, Custom) to provide
    standard embed_documents and embed_query methods.
    
    Note: Cannot use ThreadSafeSingleton metaclass due to Embeddings
    metaclass conflict, so uses module-level singleton pattern.
    
    Dimension is auto-detected from actual embedding output.
    
    Attributes:
        provider_type: Current provider type (local, openai, custom)
        model_name: Model identifier
        device: Compute device (cpu/cuda)
    """
    
    def __init__(
        self, 
        model_name: Optional[str] = None, 
        device: str = "cpu",
        provider: Optional[str] = None,
    ):
        """
        Initialize embedding manager.
        
        Args:
            model_name: Model name (uses settings default if not provided)
            device: Device to run on (cpu/cuda)
            provider: Override provider type (uses settings default if not provided)
        """
        self.provider_type = provider or settings.EMBEDDING_PROVIDER
        self.device = device
        self._cached_dimension: Optional[int] = None
        self._model: Optional[Embeddings] = None
        
        # Initialize based on provider type
        self._initialize_provider(model_name)
    
    def _initialize_provider(self, model_name: Optional[str]) -> None:
        """
        Initialize the appropriate embedding provider.
        
        Args:
            model_name: Model name override
        """
        if self.provider_type == "custom":
            self._init_custom(model_name)
        elif self.provider_type == "openai":
            self._init_openai(model_name)
        else:
            # Default to Local (HuggingFace)
            self._init_local(model_name)
    
    def _init_custom(self, model_name: Optional[str]) -> None:
        """Initialize Custom API provider."""
        self.model_name = model_name or settings.EB_MODEL
        logger.info(f"Initializing Custom Embeddings: {self.model_name}")
        
        from src.infrastructure.embeddings.langchain_wrapper import CustomLangChainEmbeddings
        from src.infrastructure.embeddings.providers.custom_api_provider import get_custom_embedding_provider
        
        custom_provider = get_custom_embedding_provider()
        self._model = CustomLangChainEmbeddings(provider=custom_provider)
    
    def _init_openai(self, model_name: Optional[str]) -> None:
        """Initialize OpenAI provider."""
        self.model_name = model_name or settings.EMBEDDING_MODEL_OPENAI
        logger.info(f"Initializing OpenAI Embeddings: {self.model_name}")
        
        from langchain_openai import OpenAIEmbeddings
        
        self._model = OpenAIEmbeddings(
            model=self.model_name,
            api_key=settings.OPENAI_API_KEY,
        )
    
    def _init_local(self, model_name: Optional[str]) -> None:
        """Initialize local HuggingFace provider (default)."""
        self.model_name = model_name or settings.EMBEDDING_MODEL_LOCAL
        logger.info(f"Initializing Local HuggingFace Embeddings: {self.model_name}")
        
        from langchain_huggingface import HuggingFaceEmbeddings
        
        self._model = HuggingFaceEmbeddings(
            model_name=self.model_name,
            model_kwargs={'device': self.device},
            encode_kwargs={'normalize_embeddings': True}
        )
    
    @property
    def name(self) -> str:
        """Provider name (implements BaseProvider protocol)."""
        return f"{self.provider_type}:{self.model_name}"
    
    @property
    def dimension(self) -> int:
        """Embedding dimension size (implements EmbeddingProvider protocol)."""
        return self.get_dimension()
    
    def is_available(self) -> bool:
        """Check if provider is available (implements BaseProvider protocol)."""
        try:
            self._model.embed_query("test")
            return True
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
                "provider": self.provider_type,
                "model": self.model_name,
                "dimension": self._cached_dimension,
            }
        except Exception as e:
            return {
                "status": "error",
                "provider": self.provider_type,
                "error": str(e),
            }
    
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """
        Embed search documents.
        
        Args:
            texts: List of texts to embed
            
        Returns:
            List of embedding vectors
        """
        embeddings = self._model.embed_documents(texts)
        # Cache dimension from first embedding
        if embeddings and self._cached_dimension is None:
            self._cached_dimension = len(embeddings[0])
            logger.info(f"Auto-detected embedding dimension: {self._cached_dimension}")
        return embeddings

    def embed_query(self, text: str) -> List[float]:
        """
        Embed query text.
        
        Args:
            text: Text to embed
            
        Returns:
            Embedding vector
        """
        embedding = self._model.embed_query(text)
        # Cache dimension from embedding
        if embedding and self._cached_dimension is None:
            self._cached_dimension = len(embedding)
            logger.info(f"Auto-detected embedding dimension: {self._cached_dimension}")
        return embedding
    
    # Protocol compliance aliases
    def embed(self, text: str) -> List[float]:
        """Embed single text (implements EmbeddingProvider protocol)."""
        return self.embed_query(text)
    
    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Embed multiple texts (implements EmbeddingProvider protocol)."""
        return self.embed_documents(texts)
    
    # Backward compatibility methods
    def generate_embedding(self, text: str) -> List[float]:
        """Alias for embed_query (backward compatibility)."""
        return self.embed_query(text)
    
    def get_dimension(self) -> int:
        """
        Get embedding dimension (auto-detected from model).
        
        If dimension hasn't been cached yet, generates a test embedding
        to determine the actual dimension from the model.
        
        Returns:
            int: Embedding dimension
        """
        if self._cached_dimension is not None:
            return self._cached_dimension
        
        # Auto-detect by generating a test embedding
        try:
            test_embedding = self._model.embed_query("test")
            self._cached_dimension = len(test_embedding)
            logger.info(f"Auto-detected embedding dimension: {self._cached_dimension}")
            return self._cached_dimension
        except Exception as e:
            logger.warning(f"Could not auto-detect dimension: {e}")
            # Fallback to known defaults
            return self._get_fallback_dimension()
    
    def _get_fallback_dimension(self) -> int:
        """Get fallback dimension based on known model dimensions."""
        known_dimensions = {
            # OpenAI
            "text-embedding-ada-002": 1536,
            "text-embedding-3-small": 1536,
            "text-embedding-3-large": 3072,
            # Local HuggingFace
            "all-MiniLM-L6-v2": 384,
            "all-mpnet-base-v2": 768,
            "multi-qa-MiniLM-L6-cos-v1": 384,
            "paraphrase-MiniLM-L6-v2": 384,
        }
        
        # Check for exact match
        for model_key, dim in known_dimensions.items():
            if model_key in self.model_name:
                return dim
        
        # Default based on provider
        if self.provider_type == "openai":
            return 1536
        elif self.provider_type == "custom":
            return settings.EB_DIMENSION or 1536
        else:
            # Local: check for common patterns
            if "large" in self.model_name.lower():
                return 1024
            elif "base" in self.model_name.lower():
                return 768
            return 384  # Default for small models
        
    def get_provider_info(self) -> Dict[str, Any]:
        """
        Get provider metadata including auto-detected dimension.
        
        Returns:
            Dict with provider details
        """
        return {
            "provider": self.provider_type,
            "model": self.model_name,
            "dimension": self.get_dimension(),
            "available": self.is_available(),
        }
    
    @property
    def langchain_embeddings(self) -> Embeddings:
        """
        Return LangChain-compatible embeddings object.
        
        For VectorDB compatibility.
        """
        return self._model
    
    def get_model_name(self) -> str:
        """Get the model name."""
        return self.model_name


def get_embedding_manager(
    model_name: Optional[str] = None,
    device: str = "cpu",
    **kwargs
) -> EmbeddingManager:
    """
    Get or create global embedding manager instance.
    
    Thread-safe singleton accessor.
    
    Args:
        model_name: Model name (only used on first call)
        device: Compute device (only used on first call)
        **kwargs: Additional arguments
        
    Returns:
        EmbeddingManager singleton instance
    """
    global _embedding_manager_instance
    
    # Fast path - instance already exists
    if _embedding_manager_instance is not None:
        return _embedding_manager_instance
    
    # Slow path - need to create with lock
    with _get_lock():
        if _embedding_manager_instance is None:
            _embedding_manager_instance = EmbeddingManager(
                model_name=model_name, 
                device=device, 
                **kwargs
            )
        return _embedding_manager_instance


def reset_embedding_manager() -> None:
    """
    Reset the embedding manager singleton.
    
    Useful for testing or reconfiguration.
    """
    global _embedding_manager_instance
    with _get_lock():
        _embedding_manager_instance = None

