"""
Models - LLM module.

Provides unified interface for LLM providers:
- OpenAI (GPT-4, GPT-3.5)
- Ollama (local models)
- Custom API (bearer token auth)

Usage:
    from models.llm import get_llm_provider
    
    # Auto-loads from settings.LLM_PROVIDER
    llm = get_llm_provider()
"""

# Will be populated after moving LLM files

__all__ = []
