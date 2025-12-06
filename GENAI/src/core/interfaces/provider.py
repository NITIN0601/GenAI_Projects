"""
Provider interface definitions using Python Protocols.

These protocols define the contract that all providers must implement,
enabling type-safe duck typing and easy provider swapping.

Providers: Local, OpenAI, Custom (as configured in settings)
"""

from typing import Any, Dict, List, Optional, Protocol, runtime_checkable
from abc import abstractmethod


@runtime_checkable
class BaseProvider(Protocol):
    """
    Base protocol for all providers.
    
    All providers must implement:
    - name: Provider identifier
    - is_available(): Check if provider is ready
    - health_check(): Verify provider status
    """
    
    @property
    def name(self) -> str:
        """Provider name identifier."""
        ...
    
    def is_available(self) -> bool:
        """Check if provider is available and ready."""
        ...
    
    def health_check(self) -> Dict[str, Any]:
        """
        Perform health check.
        
        Returns:
            Dict with 'status' (ok/error) and optional details
        """
        ...


@runtime_checkable
class LLMProvider(BaseProvider, Protocol):
    """
    Protocol for LLM providers (Local, OpenAI, Custom).
    
    Implementations: OllamaProvider, OpenAIProvider, CustomLLMProvider
    """
    
    @property
    def model(self) -> str:
        """Model name/identifier."""
        ...
    
    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs: Any
    ) -> str:
        """
        Generate text completion.
        
        Args:
            prompt: User prompt
            system_prompt: Optional system instruction
            temperature: Sampling temperature (0.0-1.0)
            max_tokens: Maximum tokens to generate
            **kwargs: Provider-specific options
            
        Returns:
            Generated text
        """
        ...
    
    async def agenerate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs: Any
    ) -> str:
        """Async version of generate."""
        ...
    
    def stream(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs: Any
    ):
        """
        Stream text generation.
        
        Yields:
            Text chunks as they're generated
        """
        ...


@runtime_checkable
class EmbeddingProvider(BaseProvider, Protocol):
    """
    Protocol for embedding providers (Local, OpenAI, Custom).
    
    Implementations: LocalEmbedding, OpenAIEmbedding, CustomEmbedding
    """
    
    @property
    def dimension(self) -> int:
        """Embedding dimension size."""
        ...
    
    def embed(self, text: str) -> List[float]:
        """
        Generate embedding for single text.
        
        Args:
            text: Text to embed
            
        Returns:
            Embedding vector
        """
        ...
    
    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for multiple texts.
        
        Args:
            texts: List of texts to embed
            
        Returns:
            List of embedding vectors
        """
        ...


@runtime_checkable
class VectorStoreProvider(BaseProvider, Protocol):
    """
    Protocol for vector store providers (FAISS, ChromaDB, Redis).
    
    Implementations: FAISSStore, ChromaDBStore, RedisVectorStore
    """
    
    @property
    def collection_name(self) -> str:
        """Collection/index name."""
        ...
    
    def add(
        self,
        ids: List[str],
        embeddings: List[List[float]],
        metadatas: Optional[List[Dict[str, Any]]] = None,
        documents: Optional[List[str]] = None,
    ) -> None:
        """Add vectors to store."""
        ...
    
    def search(
        self,
        query_embedding: List[float],
        top_k: int = 5,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Search for similar vectors.
        
        Returns:
            List of results with 'id', 'score', 'metadata', 'document'
        """
        ...
    
    def delete(self, ids: List[str]) -> None:
        """Delete vectors by ID."""
        ...
    
    def count(self) -> int:
        """Get total vector count."""
        ...


@runtime_checkable
class ExtractionProvider(BaseProvider, Protocol):
    """
    Protocol for PDF extraction backends.
    
    Implementations: DoclingBackend, PyMuPDFBackend, PDFPlumberBackend
    """
    
    def extract(
        self,
        pdf_path: str,
        **kwargs: Any
    ) -> Dict[str, Any]:
        """
        Extract tables from PDF.
        
        Returns:
            Dict with 'tables', 'metadata', 'quality_score'
        """
        ...
    
    def get_supported_features(self) -> List[str]:
        """Get list of supported extraction features."""
        ...
