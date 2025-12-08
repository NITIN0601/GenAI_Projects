"""
LangChain Wrappers for Custom Embedding Providers.

Provides adapter classes to make custom API providers compatible with
LangChain's Embeddings interface.
"""

from typing import List

from langchain_core.embeddings import Embeddings

from src.utils import get_logger

logger = get_logger(__name__)


class CustomLangChainEmbeddings(Embeddings):
    """
    Wrapper to make CustomAPIEmbeddingProvider compatible with LangChain.
    
    Adapts the custom provider's interface to LangChain's Embeddings interface.
    
    Example:
        >>> from src.infrastructure.embeddings.providers.custom_api_provider import get_custom_embedding_provider
        >>> provider = get_custom_embedding_provider()
        >>> wrapper = CustomLangChainEmbeddings(provider=provider)
        >>> embedding = wrapper.embed_query("Hello world")
    """
    
    def __init__(self, provider):
        """
        Initialize the wrapper.
        
        Args:
            provider: Custom embedding provider instance with generate_embedding() 
                     and generate_embeddings_batch() methods
        """
        self.provider = provider
    
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """
        Embed a list of documents.
        
        Args:
            texts: List of texts to embed
            
        Returns:
            List of embedding vectors
        """
        return self.provider.generate_embeddings_batch(texts)
        
    def embed_query(self, text: str) -> List[float]:
        """
        Embed a single query text.
        
        Args:
            text: Text to embed
            
        Returns:
            Embedding vector
        """
        return self.provider.generate_embedding(text)
