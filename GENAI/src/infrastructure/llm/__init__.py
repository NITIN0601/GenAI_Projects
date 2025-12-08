"""
LLM Integration Module.

Provides unified interface for multiple LLM providers using LangChain:
- Ollama (local, default)
- OpenAI (GPT-4, GPT-3.5-turbo)
- Custom APIs (bearer token)
- Local HuggingFace models

Thread-Safe Singleton:
    The LLMManager uses ThreadSafeSingleton pattern for consistent
    instance management across the application.

Example:
    >>> from src.infrastructure.llm import get_llm_manager
    >>> 
    >>> # Get singleton instance
    >>> llm = get_llm_manager()
    >>> response = llm.generate("What is RAG?")
    >>> 
    >>> # Stream response
    >>> for chunk in llm.stream("Explain AI"):
    ...     print(chunk, end="")
    
For direct provider access without LangChain:
    >>> from src.infrastructure.llm.providers import OllamaLLMProvider
    >>> provider = OllamaLLMProvider(model="llama3.2")
"""

from src.infrastructure.llm.manager import (
    LLMManager,
    get_llm_manager,
    reset_llm_manager,
)
from src.infrastructure.llm.langchain_wrapper import CustomLangChainWrapper

__version__ = "2.1.0"

__all__ = [
    # Manager
    'LLMManager',
    'get_llm_manager',
    'reset_llm_manager',
    # Wrappers
    'CustomLangChainWrapper',
]
