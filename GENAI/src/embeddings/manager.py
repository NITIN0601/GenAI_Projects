"""
Embedding manager using LangChain.

Standardizes embedding generation using LangChain's interface.
Supports:
- Local (HuggingFace via LangChain)
- OpenAI (via LangChain)
- Custom API (via Custom Provider)

Dimension is auto-detected from actual model output.
"""

from typing import List, Optional, Any
import logging
from langchain_core.embeddings import Embeddings
from langchain_huggingface import HuggingFaceEmbeddings

from config.settings import settings
from src.embeddings.providers.custom_api_provider import get_custom_embedding_provider

logger = logging.getLogger(__name__)


class CustomLangChainEmbeddings(Embeddings):
    """Wrapper to make CustomAPIEmbeddingProvider compatible with LangChain."""
    
    def __init__(self, provider):
        self.provider = provider
    
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return self.provider.generate_embeddings_batch(texts)
        
    def embed_query(self, text: str) -> List[float]:
        return self.provider.generate_embedding(text)


class EmbeddingManager(Embeddings):
    """
    Unified Embedding Manager implementing LangChain interface.
    
    Wraps specific providers (HuggingFace, OpenAI, Custom) to provide
    standard embed_documents and embed_query methods.
    
    Dimension is auto-detected from actual embedding output.
    """
    
    def __init__(self, model_name: Optional[str] = None, device: str = "cpu"):
        """
        Initialize embedding manager.
        
        Args:
            model_name: Model name (default from settings)
            device: Device to run on (cpu/cuda)
        """
        self.provider_type = settings.EMBEDDING_PROVIDER
        self.device = device
        self._cached_dimension: Optional[int] = None
        
        if self.provider_type == "custom":
            self.model_name = model_name or settings.EB_MODEL
            logger.info(f"Initializing Custom Embeddings: {self.model_name}")
            
            custom_provider = get_custom_embedding_provider()
            self._model = CustomLangChainEmbeddings(provider=custom_provider)
            
        elif self.provider_type == "openai":
            self.model_name = model_name or settings.EMBEDDING_MODEL_OPENAI
            logger.info(f"Initializing OpenAI Embeddings: {self.model_name}")
            
            from langchain_openai import OpenAIEmbeddings
            self._model = OpenAIEmbeddings(
                model=self.model_name,
                api_key=settings.OPENAI_API_KEY,
            )
            
        else:
            # Default to Local (HuggingFace)
            self.model_name = model_name or settings.EMBEDDING_MODEL_LOCAL
            logger.info(f"Initializing LangChain Local Embeddings: {self.model_name}")
            
            self._model = HuggingFaceEmbeddings(
                model_name=self.model_name,
                model_kwargs={'device': self.device},
                encode_kwargs={'normalize_embeddings': True}
            )
        
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Embed search docs."""
        embeddings = self._model.embed_documents(texts)
        # Cache dimension from first embedding
        if embeddings and self._cached_dimension is None:
            self._cached_dimension = len(embeddings[0])
            logger.info(f"Auto-detected embedding dimension: {self._cached_dimension}")
        return embeddings

    def embed_query(self, text: str) -> List[float]:
        """Embed query text."""
        embedding = self._model.embed_query(text)
        # Cache dimension from embedding
        if embedding and self._cached_dimension is None:
            self._cached_dimension = len(embedding)
            logger.info(f"Auto-detected embedding dimension: {self._cached_dimension}")
        return embedding
        
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
        # Known model dimensions
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
        
    def get_provider_info(self) -> dict:
        """Get provider metadata including auto-detected dimension."""
        return {
            "provider": self.provider_type,
            "model": self.model_name,
            "dimension": self.get_dimension()
        }
    
    @property
    def langchain_embeddings(self) -> Embeddings:
        """Return LangChain-compatible embeddings object (for VectorDB compatibility)."""
        return self._model
    
    def get_model_name(self) -> str:
        """Get the model name."""
        return self.model_name


# Global instance
_embedding_manager: Optional[EmbeddingManager] = None

def get_embedding_manager() -> EmbeddingManager:
    """Get global embedding manager."""
    global _embedding_manager
    if _embedding_manager is None:
        _embedding_manager = EmbeddingManager()
    return _embedding_manager

