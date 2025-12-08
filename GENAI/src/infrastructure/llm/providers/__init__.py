"""
LLM Providers Package.

Provides direct LLM provider implementations for use cases where
LangChain is not needed. For LangChain integration, use:
    from src.infrastructure.llm import get_llm_manager

Available Providers:
- OpenAILLMProvider: GPT-4, GPT-3.5-turbo
- OllamaLLMProvider: Local Ollama models
- CustomAPILLMProvider: Custom bearer token API

Example:
    >>> from src.infrastructure.llm.providers import OllamaLLMProvider
    >>> 
    >>> provider = OllamaLLMProvider(model="llama3.2")
    >>> response = provider.generate("Hello!")
"""

from src.infrastructure.llm.providers.base import (
    LLMProvider,
    OpenAILLMProvider,
    OllamaLLMProvider,
    create_openai_provider,
    create_ollama_provider,
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
    # Base
    'LLMProvider',
    'BaseLLMProvider',
    # Providers
    'OpenAILLMProvider',
    'OllamaLLMProvider',
    'CustomAPILLMProvider',
    # Factory functions
    'create_openai_provider',
    'create_ollama_provider',
]
