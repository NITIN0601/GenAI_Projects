"""
Domain-Specific Patterns for Financial Document Processing.

This module centralizes all domain-specific patterns that are used across
the extraction pipeline. By externalizing these patterns, the system can be
adapted for different clients/domains without modifying core logic.

Usage:
    from src.utils.domain_patterns import (
        VALID_SECTION_STARTERS,
        BUSINESS_SEGMENTS,
        DATE_HEADER_PATTERNS,
    )

To customize for a different domain:
1. Create a new file (e.g., domain_patterns_xyz.py)
2. Define the same constants with domain-specific values
3. Update imports in extraction_utils.py and consolidated_exporter.py
"""

# =============================================================================
# SECTION DETECTION PATTERNS
# =============================================================================

# Words that typically start section titles in financial documents
# Used to distinguish actual sections from footnotes in TOC parsing
VALID_SECTION_STARTERS = [
    # General document sections
    'introduction', 'executive', 'business', 'supplemental', 
    'accounting', 'critical', 'liquidity', 'balance', 'regulatory',
    
    # Analysis sections
    'quantitative', 'qualitative', 'market', 'credit', 'country',
    
    # Report sections
    'report', 'consolidated', 'notes', 'financial', 'controls', 
    'legal', 'risk', 'other', 'exhibits', 'signatures',
    
    # Financial statement line items (section headers)
    'cash', 'fair', 'derivative', 'securities', 'collateral', 'loans',
    'deposits', 'borrowings', 'commitments', 'variable', 'total', 'equity',
    'interest', 'income', 'taxes', 'segment', 'geographic', 'revenue',
    'basis', 'presentation', 'policies', 'assets', 'liabilities',
    
    # Client-specific business segments (Morgan Stanley)
    'institutional', 'wealth', 'investment',
]

# Words that indicate footnotes (NOT section headers)
# Used to filter out footnote text when parsing TOC
FOOTNOTE_INDICATORS = [
    'amounts', 'includes', 'based on', 'represents', 'related to',
    'percent', 'excludes', 'primarily', 'net of', 'see note',
    'does not', 'prior to', 'inclusive of', 'applicable',
]


# =============================================================================
# BUSINESS SEGMENT NAMES
# =============================================================================

# Top-level business segments used for section grouping
# These are client-specific (currently Morgan Stanley)
BUSINESS_SEGMENTS = [
    'institutional securities',
    'wealth management', 
    'investment management',
    'corporate',
    'intersegment eliminations',
    'inter-segment eliminations',
]

# General section headers (more generic, less client-specific)
GENERAL_SECTION_HEADERS = [
    "management's discussion and analysis",
    'consolidated financial statements',
    'notes to consolidated financial statements',
    'risk disclosures',
    'financial data supplement',
]


# =============================================================================
# DATE/PERIOD HEADER PATTERNS
# =============================================================================

# Patterns that identify header rows containing date/period information
# Used in consolidated_exporter to detect embedded table headers
DATE_HEADER_PATTERNS = [
    # Period patterns
    'three months ended',
    'six months ended',
    'nine months ended',
    'twelve months ended',
    'fiscal year ended',
    'year ended',
    
    # "At" date patterns (balance sheet dates)
    'at march', 'at june', 'at september', 'at december',
    'at january', 'at february', 'at april', 'at may',
    'at july', 'at august', 'at october', 'at november',
]

# Year range for detecting year-only header rows (from settings for .env configurability)
from config.settings import settings
VALID_YEAR_RANGE = (settings.EXTRACTION_YEAR_MIN, settings.EXTRACTION_YEAR_MAX)


# =============================================================================
# TABLE CLASSIFICATION PATTERNS
# =============================================================================

# Units and measurement indicators (not business entities)
UNIT_INDICATORS = [
    'dollars in millions',
    'dollars in billions', 
    'dollars in thousands',
    'in millions',
    'in billions',
    'in thousands',
    '$ in millions',
    '$ in billions',
    'in %',
    'percentage',
    'ratio',
]

# =============================================================================
# TABLE MERGER PATTERNS (used in table_merger.py header detection)
# =============================================================================

# Patterns that indicate a header row (used in table merging)
TABLE_HEADER_PATTERNS = [
    '$ in millions', '$ in billions', '$ in thousands',
    'three months ended', 'six months ended', 'nine months ended',
    'at june', 'at december', 'at march', 'at september',
    'trading', 'fees', 'net interest', 'total'
]

# Patterns that indicate actual data row labels (NOT headers)
DATA_LABEL_PATTERNS = [
    'financing', 'execution', 'equity', 'fixed income',
    'common', 'tangible', 'average', 'assets', 'liabilities',
    'revenues', 'expenses', 'income', 'loss'
]


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def is_valid_section_starter(text: str) -> bool:
    """Check if text starts with a valid section indicator."""
    text_lower = text.lower()
    first_word = text_lower.split()[0] if text_lower.split() else ''
    return any(first_word.startswith(starter) for starter in VALID_SECTION_STARTERS)


def is_footnote_indicator(text: str) -> bool:
    """Check if text indicates a footnote rather than a section."""
    text_lower = text.lower()
    return any(text_lower.startswith(indicator) for indicator in FOOTNOTE_INDICATORS)


def is_business_segment(text: str) -> bool:
    """Check if text matches a known business segment."""
    text_lower = text.lower()
    return any(seg in text_lower for seg in BUSINESS_SEGMENTS)


def is_date_header_row(label: str) -> bool:
    """Check if a row label indicates a date/period header."""
    label_lower = label.lower() if label else ''
    return any(pattern in label_lower for pattern in DATE_HEADER_PATTERNS)


def is_year_value(value: str) -> bool:
    """Check if value is a standalone year within valid range."""
    if value.isdigit() and len(value) == 4:
        year = int(value)
        return VALID_YEAR_RANGE[0] <= year <= VALID_YEAR_RANGE[1]
    return False
