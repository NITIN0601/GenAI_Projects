"""LLM providers."""

from src.infrastructure.llm.providers.base import (
    LLMProvider,
    OpenAILLMProvider,
    OllamaLLMProvider,
)

# Alias for compatibility
BaseLLMProvider = LLMProvider

# Lazy import to avoid circular dependency
def __getattr__(name):
    if name == 'CustomAPILLMProvider':
        from src.infrastructure.embeddings.providers.custom_api_provider import CustomAPILLMProvider
        return CustomAPILLMProvider
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = [
    'LLMProvider',
    'BaseLLMProvider',
    'OpenAILLMProvider',
    'OllamaLLMProvider',
    'CustomAPILLMProvider',
]
