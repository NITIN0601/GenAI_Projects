"""
LLM integration module.

Provides unified interface for multiple LLM providers:
- Ollama (local)
- Custom APIs

Example:
    >>> from src.infrastructure.llm import LLMManager
    >>> manager = LLMManager(provider="ollama")
    >>> response = manager.generate("What is RAG?")
"""

from src.infrastructure.llm.manager import LLMManager, get_llm_manager

__version__ = "2.0.0"

__all__ = [
    'LLMManager',
    'get_llm_manager',
]
