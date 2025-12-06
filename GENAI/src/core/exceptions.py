"""
Centralized exception hierarchy for GENAI RAG system.

All custom exceptions inherit from GENAIException for easy catch-all handling.
Each exception type corresponds to a specific subsystem.

Example:
    >>> from src.core import ExtractionError
    >>> raise ExtractionError("Failed to parse table", pdf_path="doc.pdf")
"""

from typing import Any, Optional


class GENAIException(Exception):
    """
    Base exception for all GENAI errors.
    
    Attributes:
        message: Human-readable error message
        details: Additional context (optional)
    """
    
    def __init__(self, message: str, **details: Any):
        self.message = message
        self.details = details
        super().__init__(message)
    
    def __str__(self) -> str:
        if self.details:
            detail_str = ", ".join(f"{k}={v}" for k, v in self.details.items())
            return f"{self.message} ({detail_str})"
        return self.message


# =========================================================================
# Extraction Errors
# =========================================================================

class ExtractionError(GENAIException):
    """Error during PDF extraction."""
    pass


class PDFNotFoundError(ExtractionError):
    """PDF file not found."""
    pass


class UnsupportedFormatError(ExtractionError):
    """Unsupported file format."""
    pass


class BackendNotAvailableError(ExtractionError):
    """Requested extraction backend is not available."""
    pass


class QualityThresholdError(ExtractionError):
    """Extraction quality is below threshold."""
    pass


class ParsingError(ExtractionError):
    """Document parsing failed."""
    pass


# =========================================================================
# Embedding Errors
# =========================================================================

class EmbeddingError(GENAIException):
    """Error during embedding generation."""
    pass


class EmbeddingModelError(EmbeddingError):
    """Error loading or using embedding model."""
    pass


class EmbeddingDimensionError(EmbeddingError):
    """Embedding dimension mismatch."""
    pass


class EmbeddingProviderError(EmbeddingError):
    """Embedding provider failed."""
    pass


# =========================================================================
# Vector Store Errors
# =========================================================================

class VectorStoreError(GENAIException):
    """Error with vector database operations."""
    pass


class VectorStoreConnectionError(VectorStoreError):
    """Failed to connect to vector store."""
    pass


class VectorStoreQueryError(VectorStoreError):
    """Error executing vector query."""
    pass


class VectorStoreIndexError(VectorStoreError):
    """Vector store index operations failed."""
    pass


# =========================================================================
# LLM Errors
# =========================================================================

class LLMError(GENAIException):
    """Error with LLM operations."""
    pass


class LLMConnectionError(LLMError):
    """Failed to connect to LLM provider."""
    pass


class LLMRateLimitError(LLMError):
    """Rate limit exceeded."""
    pass


class LLMTokenLimitError(LLMError):
    """Token limit exceeded."""
    pass


class LLMProviderError(LLMError):
    """LLM provider failed."""
    pass


class LLMResponseError(LLMError):
    """LLM response is invalid."""
    pass


class LLMTimeoutError(LLMError):
    """LLM request timed out."""
    pass


# =========================================================================
# RAG Pipeline Errors
# =========================================================================

class RAGError(GENAIException):
    """Error in RAG pipeline."""
    pass


class RetrievalError(RAGError):
    """Error during retrieval phase."""
    pass


class GenerationError(RAGError):
    """Error during generation phase."""
    pass


class ContextBuildingError(RAGError):
    """Error building context."""
    pass


class ResponseGenerationError(RAGError):
    """Error generating response."""
    pass


# =========================================================================
# Cache Errors
# =========================================================================

class CacheError(GENAIException):
    """Error with caching operations."""
    pass


class CacheCorruptionError(CacheError):
    """Cache data is corrupted."""
    pass


class CacheMissError(CacheError):
    """Expected cache entry not found."""
    pass


class CacheConnectionError(CacheError):
    """Cache connection failed."""
    pass


# =========================================================================
# Ingestion Errors
# =========================================================================

class IngestionError(GENAIException):
    """Error during ingestion."""
    pass


class ScraperError(IngestionError):
    """Web scraping failed."""
    pass


class DocumentLoaderError(IngestionError):
    """Document loading failed."""
    pass


# =========================================================================
# Validation Errors
# =========================================================================

class ValidationError(GENAIException):
    """Input validation failed."""
    pass


class QueryValidationError(ValidationError):
    """Invalid query parameters."""
    pass


class ConfigValidationError(ValidationError):
    """Invalid configuration."""
    pass


# =========================================================================
# Configuration Errors
# =========================================================================

class ConfigurationError(GENAIException):
    """Configuration is invalid."""
    pass


class MissingAPIKeyError(ConfigurationError):
    """Required API key is missing."""
    pass


# =========================================================================
# Provider Errors
# =========================================================================

class ProviderError(GENAIException):
    """Error with external provider."""
    pass


class ProviderNotFoundError(ProviderError):
    """Requested provider not found."""
    pass


class ProviderConfigError(ProviderError):
    """Provider configuration invalid."""
    pass
