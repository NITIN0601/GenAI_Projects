"""
Unified prompt templates module.

This module provides a centralized location for all prompt templates used
throughout the GENAI system. Prompts are organized by purpose:

- base: Core financial analysis prompts
- retrieval: Search strategy prompts (HyDE, Multi-Query)
- advanced: Advanced reasoning techniques (CoT, ReAct)
- few_shot: Few-shot learning examples and management

Usage:
    from src.prompts import FINANCIAL_ANALYSIS_PROMPT, HYDE_PROMPT
    from src.prompts import get_few_shot_manager
"""

# Base prompts
from .base import (
    FINANCIAL_ANALYSIS_PROMPT,
    FINANCIAL_CHAT_PROMPT,
    TABLE_COMPARISON_PROMPT,
    METADATA_EXTRACTION_PROMPT,
    CITATION_PROMPT
)

# Retrieval prompts
from src.prompts.search_strategies import HYDE_PROMPT, MULTI_QUERY_PROMPT

# Advanced prompts
from .advanced import (
    COT_PROMPT,
    REACT_PROMPT
)

# Few-shot learning
from .few_shot import (
    FINANCIAL_EXAMPLES,
    EXAMPLE_TEMPLATE,
    FewShotManager,
    get_few_shot_manager
)


__all__ = [
    # Base prompts
    'FINANCIAL_ANALYSIS_PROMPT',
    'FINANCIAL_CHAT_PROMPT',
    'TABLE_COMPARISON_PROMPT',
    'METADATA_EXTRACTION_PROMPT',
    'CITATION_PROMPT',
    
    # Retrieval prompts
    'HYDE_PROMPT',
    'MULTI_QUERY_PROMPT',
    
    # Advanced prompts
    'COT_PROMPT',
    'REACT_PROMPT',
    
    # Few-shot learning
    'FINANCIAL_EXAMPLES',
    'EXAMPLE_TEMPLATE',
    'FewShotManager',
    'get_few_shot_manager',
]
