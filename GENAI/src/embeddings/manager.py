"""
Embedding manager using LangChain.

Standardizes embedding generation using LangChain's interface.
Supports:
- Local (HuggingFace via LangChain)
- OpenAI (via LangChain)
- Custom API (via Custom Provider)
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
        
        elif self.provider_type == "custom":
            self.model_name = model_name or settings.EB_MODEL
            logger.info(f"Initializing Custom Embeddings: {self.model_name}")
            
            custom_provider = get_custom_embedding_provider()
            self._model = CustomLangChainEmbeddings(provider=custom_provider)
            
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
        return self._model.embed_documents(texts)

    def embed_query(self, text: str) -> List[float]:
        """Embed query text."""
        return self._model.embed_query(text)
        
    # Backward compatibility methods
    def generate_embedding(self, text: str) -> List[float]:
        """Alias for embed_query (backward compatibility)."""
        return self.embed_query(text)
        
    def get_provider_info(self) -> dict:
        """Get provider metadata."""
        if self.provider_type == "custom":
            # Try to get dimension from the underlying provider
            dim = 384
            if hasattr(self._model, 'provider') and hasattr(self._model.provider, 'get_dimension'):
                dim = self._model.provider.get_dimension()
                
            return {
                "provider": "custom",
                "model": self.model_name,
                "dimension": dim
            }
            
        # Default dimensions for common models
        dim = 384 # Default for MiniLM
        if "base" in self.model_name:
            dim = 768
        elif "large" in self.model_name:
            dim = 1024
            
        return {
            "provider": "langchain_huggingface",
            "model": self.model_name,
            "dimension": dim
        }


# Global instance
_embedding_manager: Optional[EmbeddingManager] = None

def get_embedding_manager() -> EmbeddingManager:
    """Get global embedding manager."""
    global _embedding_manager
    if _embedding_manager is None:
        _embedding_manager = EmbeddingManager()
    return _embedding_manager
