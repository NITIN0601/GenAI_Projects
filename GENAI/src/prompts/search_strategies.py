"""
Retrieval strategy prompt templates.

This module contains prompts for advanced retrieval strategies:
- HyDE (Hypothetical Document Embeddings)
- Multi-Query (Query Expansion)

Refactored to load prompts from config/prompts.yaml via PromptLoader.
"""

from src.prompts.loader import get_prompt_loader

# Initialize loader
_loader = get_prompt_loader()

# ============================================================================
# HYDE PROMPT
# ============================================================================

HYDE_PROMPT = _loader.get_prompt_template("hyde")


# ============================================================================
# MULTI-QUERY PROMPT
# ============================================================================

MULTI_QUERY_PROMPT = _loader.get_prompt_template("multi_query")


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    'HYDE_PROMPT',
    'MULTI_QUERY_PROMPT',
]
