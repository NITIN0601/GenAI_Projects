"""
Provider abstraction layer for embeddings.

Supports:
- OpenAI (text-embedding-3-small, text-embedding-ada-002)
- Local (sentence-transformers)
- Easy switching via configuration
"""

from abc import ABC, abstractmethod
from typing import List, Optional
import os

from src.utils import get_logger

logger = get_logger(__name__)

class EmbeddingProvider(ABC):
    """Abstract base class for embedding providers."""
    
    @abstractmethod
    def generate_embedding(self, text: str) -> List[float]:
        """Generate embedding for single text."""
        pass
    
    @abstractmethod
    def generate_embeddings_batch(
        self,
        texts: List[str],
        show_progress: bool = True
    ) -> List[List[float]]:
        """Generate embeddings for multiple texts."""
        pass
    
    @abstractmethod
    def get_dimension(self) -> int:
        """Get embedding dimension."""
        pass
    
    @abstractmethod
    def get_provider_name(self) -> str:
        """Get provider name."""
        pass


class OpenAIEmbeddingProvider(EmbeddingProvider):
    """OpenAI embedding provider."""
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "text-embedding-3-small"
    ):
        """
        Initialize OpenAI embedding provider.
        
        Args:
            api_key: OpenAI API key (or set OPENAI_API_KEY env var)
            model: Model name (text-embedding-3-small, text-embedding-ada-002)
        """
        try:
            import openai
        except ImportError:
            raise ImportError(
                "OpenAI package not installed. Install with: pip install openai"
            )
        
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError(
                "OpenAI API key required. Set OPENAI_API_KEY environment variable "
                "or pass api_key parameter"
            )
        
        self.model = model
        self.client = openai.OpenAI(api_key=self.api_key)
        
        # Set dimensions based on model
        self.dimensions = {
            "text-embedding-3-small": 1536,
            "text-embedding-3-large": 3072,
            "text-embedding-ada-002": 1536
        }
        
        logger.info(f"OpenAI Embeddings initialized: {model}")
    
    def generate_embedding(self, text: str) -> List[float]:
        """Generate embedding for single text."""
        response = self.client.embeddings.create(
            model=self.model,
            input=text
        )
        return response.data[0].embedding
    
    def generate_embeddings_batch(
        self,
        texts: List[str],
        show_progress: bool = True
    ) -> List[List[float]]:
        """Generate embeddings for multiple texts."""
        # OpenAI supports batch processing natively
        response = self.client.embeddings.create(
            model=self.model,
            input=texts
        )
        return [item.embedding for item in response.data]
    
    def get_dimension(self) -> int:
        """Get embedding dimension."""
        return self.dimensions.get(self.model, 1536)
    
    def get_provider_name(self) -> str:
        """Get provider name."""
        return f"openai-{self.model}"


class LocalEmbeddingProvider(EmbeddingProvider):
    """Local embedding provider using sentence-transformers."""
    
    def __init__(self, model_name: str = "sentence-transformers/all-MiniLM-L6-v2"):
        """
        Initialize local embedding provider.
        
        Args:
            model_name: sentence-transformers model name
        """
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError:
            raise ImportError(
                "sentence-transformers not installed. "
                "Install with: pip install sentence-transformers"
            )
        
        self.model_name = model_name
        self.model = SentenceTransformer(model_name)
        self.dimension = self.model.get_sentence_embedding_dimension()
        
        logger.info(f"Local Embeddings initialized: {model_name}")
    
    def generate_embedding(self, text: str) -> List[float]:
        """Generate embedding for single text."""
        embedding = self.model.encode(text, convert_to_numpy=True)
        return embedding.tolist()
    
    def generate_embeddings_batch(
        self,
        texts: List[str],
        show_progress: bool = True
    ) -> List[List[float]]:
        """Generate embeddings for multiple texts."""
        embeddings = self.model.encode(
            texts,
            batch_size=32,
            show_progress_bar=show_progress,
            convert_to_numpy=True
        )
        return embeddings.tolist()
    
    def get_dimension(self) -> int:
        """Get embedding dimension."""
        return self.dimension
    
    def get_provider_name(self) -> str:
        """Get provider name."""
        return f"local-{self.model_name}"


class EmbeddingManager:
    """
    Unified embedding manager with provider abstraction.
    
    Supports:
    - OpenAI (cloud, paid)
    - Local (sentence-transformers, free)
    """
    
    def __init__(
        self,
        provider: str = "local",
        model: Optional[str] = None,
        api_key: Optional[str] = None
    ):
        """
        Initialize embedding manager.
        
        Args:
            provider: "openai", "local", or "custom"
            model: Model name (provider-specific)
            api_key: API key for cloud providers
        """
        self.provider_name = provider.lower()
        
        if self.provider_name == "openai":
            model = model or "text-embedding-3-small"
            self.provider = OpenAIEmbeddingProvider(api_key=api_key, model=model)
        elif self.provider_name == "local":
            model = model or "sentence-transformers/all-MiniLM-L6-v2"
            self.provider = LocalEmbeddingProvider(model_name=model)
        elif self.provider_name == "custom":
            # Import custom provider
            from embeddings.custom_api_provider import CustomAPIEmbeddingProvider
            self.provider = CustomAPIEmbeddingProvider()
        else:
            raise ValueError(
                f"Unknown provider: {provider}. "
                f"Supported: 'openai', 'local', 'custom'"
            )
        
        logger.info(f"Embedding Manager: {self.provider.get_provider_name()}")
        logger.info(f"Dimension: {self.provider.get_dimension()}")
    
    def generate_embedding(self, text: str) -> List[float]:
        """Generate embedding for single text."""
        return self.provider.generate_embedding(text)
    
    def generate_embeddings_batch(
        self,
        texts: List[str],
        show_progress: bool = True
    ) -> List[List[float]]:
        """Generate embeddings for multiple texts."""
        return self.provider.generate_embeddings_batch(texts, show_progress)
    
    def get_dimension(self) -> int:
        """Get embedding dimension."""
        return self.provider.get_dimension()
    
    def get_provider_info(self) -> dict:
        """Get provider information."""
        return {
            "provider": self.provider_name,
            "model": self.provider.get_provider_name(),
            "dimension": self.provider.get_dimension()
        }


# Global instance
_embedding_manager: Optional[EmbeddingManager] = None


def get_embedding_manager(
    provider: Optional[str] = None,
    model: Optional[str] = None,
    api_key: Optional[str] = None
) -> EmbeddingManager:
    """
    Get or create global embedding manager.
    
    Args:
        provider: "openai" or "local" (default: from config)
        model: Model name (default: from config)
        api_key: API key for cloud providers
    """
    global _embedding_manager
    
    # Use config if not specified
    if provider is None:
        from config.settings import settings
        provider = getattr(settings, 'EMBEDDING_PROVIDER', 'local')
    
    if _embedding_manager is None:
        _embedding_manager = EmbeddingManager(
            provider=provider,
            model=model,
            api_key=api_key
        )
    
    return _embedding_manager
