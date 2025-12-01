"""
Embedding manager using LangChain.

Standardizes embedding generation using LangChain's interface.
Supports:
- Local (HuggingFace via LangChain)
- OpenAI (via LangChain)
"""

from typing import List, Optional, Any
import logging
from langchain_core.embeddings import Embeddings
from langchain_huggingface import HuggingFaceEmbeddings
# from langchain_openai import OpenAIEmbeddings # Uncomment if OpenAI needed

from config.settings import settings

logger = logging.getLogger(__name__)


class EmbeddingManager(Embeddings):
    """
    Unified Embedding Manager implementing LangChain interface.
    
    Wraps specific providers (HuggingFace, OpenAI) to provide
    standard embed_documents and embed_query methods.
    """
    
    def __init__(self, model_name: Optional[str] = None, device: str = "cpu"):
        """
        Initialize embedding manager.
        
        Args:
            model_name: Model name (default from settings)
            device: Device to run on (cpu/cuda)
        """
        self.model_name = model_name or settings.EMBEDDING_MODEL_LOCAL
        self.device = device
        
        logger.info(f"Initializing LangChain Embeddings: {self.model_name}")
        
        # Initialize underlying LangChain implementation
        # For now, defaulting to HuggingFace (Local/Free)
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
