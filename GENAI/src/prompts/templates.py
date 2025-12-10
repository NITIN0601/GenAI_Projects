"""
Consolidated Prompt Templates Module.

This module provides all prompt templates by delegating to the PromptLoader.
Replaces the separate base.py, advanced.py, and search_strategies.py files.
"""

from typing import Optional
from langchain_core.prompts import PromptTemplate, ChatPromptTemplate

from src.prompts.loader import get_prompt_loader

# Initialize loader (singleton, cached)
_loader = get_prompt_loader()


# ============================================================================
# FINANCIAL ANALYSIS PROMPTS (from base.py)
# ============================================================================

FINANCIAL_ANALYSIS_PROMPT: Optional[PromptTemplate] = _loader.get_prompt_template("financial_analysis")

FINANCIAL_CHAT_PROMPT: Optional[ChatPromptTemplate] = _loader.get_chat_prompt_template(
    "financial_chat_system", 
    "financial_chat_human"
)

TABLE_COMPARISON_PROMPT: Optional[PromptTemplate] = _loader.get_prompt_template("table_comparison")

METADATA_EXTRACTION_PROMPT: Optional[PromptTemplate] = _loader.get_prompt_template("metadata_extraction")

CITATION_PROMPT: Optional[PromptTemplate] = _loader.get_prompt_template("citation")


# ============================================================================
# ADVANCED PROMPTS (from advanced.py)
# ============================================================================

COT_PROMPT: Optional[PromptTemplate] = _loader.get_prompt_template("cot")

REACT_PROMPT: Optional[PromptTemplate] = _loader.get_prompt_template("react")


# ============================================================================
# SEARCH STRATEGY PROMPTS (from search_strategies.py)
# ============================================================================

HYDE_PROMPT: Optional[PromptTemplate] = _loader.get_prompt_template("hyde")

MULTI_QUERY_PROMPT: Optional[PromptTemplate] = _loader.get_prompt_template("multi_query")


# ============================================================================
# CONSOLIDATION PROMPTS
# ============================================================================

TIME_SERIES_CONSOLIDATION_PROMPT: Optional[PromptTemplate] = _loader.get_prompt_template("time_series_consolidation")


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    # Financial Analysis
    'FINANCIAL_ANALYSIS_PROMPT',
    'FINANCIAL_CHAT_PROMPT',
    'TABLE_COMPARISON_PROMPT',
    'METADATA_EXTRACTION_PROMPT',
    'CITATION_PROMPT',
    # Advanced
    'COT_PROMPT',
    'REACT_PROMPT',
    # Search Strategies
    'HYDE_PROMPT',
    'MULTI_QUERY_PROMPT',
    # Consolidation
    'TIME_SERIES_CONSOLIDATION_PROMPT',
]

