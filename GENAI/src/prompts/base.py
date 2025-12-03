"""
Core financial analysis prompt templates.

This module contains the base prompts for financial Q&A, table analysis,
metadata extraction, and citation formatting.

Refactored to load prompts from config/prompts.yaml via PromptLoader.
"""

from src.prompts.loader import get_prompt_loader

# Initialize loader
_loader = get_prompt_loader()

# ============================================================================
# FINANCIAL ANALYSIS PROMPTS
# ============================================================================

FINANCIAL_ANALYSIS_PROMPT = _loader.get_prompt_template("financial_analysis")

# Chat Prompt Version (for ChatModels)
FINANCIAL_CHAT_PROMPT = _loader.get_chat_prompt_template(
    "financial_chat_system", 
    "financial_chat_human"
)


# ============================================================================
# TABLE ANALYSIS PROMPTS
# ============================================================================

TABLE_COMPARISON_PROMPT = _loader.get_prompt_template("table_comparison")


# ============================================================================
# METADATA EXTRACTION PROMPTS
# ============================================================================

METADATA_EXTRACTION_PROMPT = _loader.get_prompt_template("metadata_extraction")


# ============================================================================
# CITATION PROMPTS
# ============================================================================

CITATION_PROMPT = _loader.get_prompt_template("citation")


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    'FINANCIAL_ANALYSIS_PROMPT',
    'FINANCIAL_CHAT_PROMPT',
    'TABLE_COMPARISON_PROMPT',
    'METADATA_EXTRACTION_PROMPT',
    'CITATION_PROMPT',
]
