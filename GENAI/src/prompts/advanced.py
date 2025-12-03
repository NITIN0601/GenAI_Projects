"""
Advanced prompting techniques.

This module contains prompts for advanced reasoning techniques:
- Chain-of-Thought (CoT)
- ReAct (Reasoning + Acting)

Refactored to load prompts from config/prompts.yaml via PromptLoader.
"""

from src.prompts.loader import get_prompt_loader

# Initialize loader
_loader = get_prompt_loader()

# ============================================================================
# CHAIN-OF-THOUGHT (CoT) PROMPT
# ============================================================================

COT_PROMPT = _loader.get_prompt_template("cot")


# ============================================================================
# REACT-STYLE PROMPT (Reasoning + Acting)
# ============================================================================

REACT_PROMPT = _loader.get_prompt_template("react")


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    'COT_PROMPT',
    'REACT_PROMPT',
]
