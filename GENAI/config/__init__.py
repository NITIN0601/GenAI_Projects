"""Configuration package initialization."""

from .settings import settings
from .prompts import (
    FINANCIAL_ANALYSIS_PROMPT,
    TABLE_COMPARISON_PROMPT,
    METADATA_EXTRACTION_PROMPT,
    CITATION_PROMPT
)

__all__ = [
    'settings',
    'FINANCIAL_ANALYSIS_PROMPT',
    'TABLE_COMPARISON_PROMPT',
    'METADATA_EXTRACTION_PROMPT',
    'CITATION_PROMPT'
]
