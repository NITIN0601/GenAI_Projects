"""
Custom exceptions for GENAI RAG system.

Provides a hierarchy of exceptions for different components:
- Base: GENAIException
- Extraction: ExtractionError, BackendNotAvailableError, QualityThresholdError
- Embeddings: EmbeddingError, ProviderError
- Vector Store: VectorStoreError, IndexError
- LLM: LLMError, ProviderError
- RAG: RAGError, RetrievalError
- Ingestion: IngestionError, ScraperError
"""


class GENAIException(Exception):
    """Base exception for all GENAI errors."""
    
    def __init__(self, message: str, details: dict = None):
        self.message = message
        self.details = details or {}
        super().__init__(self.message)
    
    def __str__(self):
        if self.details:
            return f"{self.message} | Details: {self.details}"
        return self.message


# ============================================================================
# EXTRACTION EXCEPTIONS
# ============================================================================

class ExtractionError(GENAIException):
    """Base exception for extraction errors."""
    pass


class BackendNotAvailableError(ExtractionError):
    """Raised when a requested extraction backend is not available."""
    pass


class QualityThresholdError(ExtractionError):
    """Raised when extraction quality is below threshold."""
    pass


class ParsingError(ExtractionError):
    """Raised when document parsing fails."""
    pass


# ============================================================================
# EMBEDDING EXCEPTIONS
# ============================================================================

class EmbeddingError(GENAIException):
    """Base exception for embedding errors."""
    pass


class EmbeddingProviderError(EmbeddingError):
    """Raised when embedding provider fails."""
    pass


class EmbeddingDimensionError(EmbeddingError):
    """Raised when embedding dimensions don't match."""
    pass


# ============================================================================
# VECTOR STORE EXCEPTIONS
# ============================================================================

class VectorStoreError(GENAIException):
    """Base exception for vector store errors."""
    pass


class VectorStoreConnectionError(VectorStoreError):
    """Raised when vector store connection fails."""
    pass


class VectorStoreIndexError(VectorStoreError):
    """Raised when vector store index operations fail."""
    pass


class VectorStoreQueryError(VectorStoreError):
    """Raised when vector store query fails."""
    pass


# ============================================================================
# LLM EXCEPTIONS
# ============================================================================

class LLMError(GENAIException):
    """Base exception for LLM errors."""
    pass


class LLMProviderError(LLMError):
    """Raised when LLM provider fails."""
    pass


class LLMResponseError(LLMError):
    """Raised when LLM response is invalid."""
    pass


class LLMTimeoutError(LLMError):
    """Raised when LLM request times out."""
    pass


# ============================================================================
# RAG EXCEPTIONS
# ============================================================================

class RAGError(GENAIException):
    """Base exception for RAG pipeline errors."""
    pass


class RetrievalError(RAGError):
    """Raised when retrieval fails."""
    pass


class ContextBuildingError(RAGError):
    """Raised when context building fails."""
    pass


class ResponseGenerationError(RAGError):
    """Raised when response generation fails."""
    pass


# ============================================================================
# INGESTION EXCEPTIONS
# ============================================================================

class IngestionError(GENAIException):
    """Base exception for ingestion errors."""
    pass


class ScraperError(IngestionError):
    """Raised when web scraping fails."""
    pass


class DocumentLoaderError(IngestionError):
    """Raised when document loading fails."""
    pass


# ============================================================================
# CACHE EXCEPTIONS
# ============================================================================

class CacheError(GENAIException):
    """Base exception for cache errors."""
    pass


class CacheConnectionError(CacheError):
    """Raised when cache connection fails."""
    pass


# ============================================================================
# CONFIGURATION EXCEPTIONS
# ============================================================================

class ConfigurationError(GENAIException):
    """Raised when configuration is invalid."""
    pass


class MissingAPIKeyError(ConfigurationError):
    """Raised when required API key is missing."""
    pass
