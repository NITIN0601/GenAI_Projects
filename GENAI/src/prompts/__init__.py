"""
Unified prompt templates module.

This module provides a centralized location for all prompt templates used
throughout the GENAI system.

Optimized Structure:
- loader.py: Loads prompts from YAML with caching
- templates.py: All prompt template constants (consolidated)
- few_shot.py: Few-shot learning examples and management

Usage:
    from src.prompts import FINANCIAL_ANALYSIS_PROMPT, HYDE_PROMPT
    from src.prompts import get_few_shot_manager
"""

# Consolidated templates (replaces base.py, advanced.py, search_strategies.py)
from .templates import (
    # Financial Analysis
    FINANCIAL_ANALYSIS_PROMPT,
    FINANCIAL_CHAT_PROMPT,
    TABLE_COMPARISON_PROMPT,
    METADATA_EXTRACTION_PROMPT,
    CITATION_PROMPT,
    # Advanced
    COT_PROMPT,
    REACT_PROMPT,
    # Search Strategies
    HYDE_PROMPT,
    MULTI_QUERY_PROMPT,
)

# Few-shot learning
from .few_shot import (
    FINANCIAL_EXAMPLES,
    EXAMPLE_TEMPLATE,
    FewShotManager,
    get_few_shot_manager
)

# Loader (for advanced usage)
from .loader import get_prompt_loader, PromptLoader


__all__ = [
    # Templates
    'FINANCIAL_ANALYSIS_PROMPT',
    'FINANCIAL_CHAT_PROMPT',
    'TABLE_COMPARISON_PROMPT',
    'METADATA_EXTRACTION_PROMPT',
    'CITATION_PROMPT',
    'COT_PROMPT',
    'REACT_PROMPT',
    'HYDE_PROMPT',
    'MULTI_QUERY_PROMPT',
    
    # Few-shot learning
    'FINANCIAL_EXAMPLES',
    'EXAMPLE_TEMPLATE',
    'FewShotManager',
    'get_few_shot_manager',
    
    # Loader
    'get_prompt_loader',
    'PromptLoader',
]
