"""
Financial Domain Patterns - Unified Pattern Configuration.

This module consolidates all domain-specific patterns for financial document processing.
It combines patterns from the former domain_patterns.py and financial_patterns.py files.

Categories:
1. Section Detection - Patterns for TOC and section parsing
2. Business Segments - Client-specific segment names
3. Date/Period - Patterns for date and quarter detection
4. Table Classification - Headers, data labels, metadata markers
5. Units & Currency - Financial units and currency detection
6. Helper Functions - Pattern matching utilities

Usage:
    from src.utils.financial_domain import (
        VALID_SECTION_STARTERS,
        DATE_HEADER_PATTERNS,
        is_year_value,
        extract_quarter_from_header,
    )

To customize for a different domain, create a new file with same exports.
"""

import re
from typing import List, Dict, Optional, Tuple

# Import year range from settings for .env configurability
from config.settings import settings
from src.utils.constants import CONSOLIDATION_YEAR_MIN, CONSOLIDATION_YEAR_MAX

__all__ = [
    # Section Detection
    'VALID_SECTION_STARTERS',
    'FOOTNOTE_INDICATORS',
    # Business Segments
    'BUSINESS_SEGMENTS',
    'GENERAL_SECTION_HEADERS',
    # Date/Period
    'DATE_HEADER_PATTERNS',
    'NEW_TABLE_HEADER_PATTERNS',
    'VALID_YEAR_RANGE',
    # Table Classification
    'UNIT_INDICATORS',
    'TABLE_HEADER_PATTERNS',
    'DATA_LABEL_PATTERNS',
    'METADATA_BOUNDARY_MARKERS',
    # Units & Currency (from financial_patterns.py)
    'UNIT_PATTERNS',
    'UNIT_PATTERNS_REGEX',
    'CURRENCY_PATTERNS',
    'STATEMENT_KEYWORDS',
    # Helper Functions
    'is_valid_section_starter',
    'is_footnote_indicator',
    'is_business_segment',
    'is_date_header_row',
    'is_year_value',
    'is_new_table_header_row',
    'extract_quarter_from_header',
    'extract_year_from_header',
    'is_10k_source',
    'convert_year_to_q4_header',
    # Unit/Currency functions (from financial_patterns.py)
    'is_unit_indicator',
    'detect_units',
    'detect_currency',
]


# =============================================================================
# SECTION DETECTION PATTERNS
# =============================================================================

# Words that typically start section titles in financial documents
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
FOOTNOTE_INDICATORS = [
    'amounts', 'includes', 'based on', 'represents', 'related to',
    'percent', 'excludes', 'primarily', 'net of', 'see note',
    'does not', 'prior to', 'inclusive of', 'applicable',
]


# =============================================================================
# BUSINESS SEGMENT NAMES
# =============================================================================

# Top-level business segments (client-specific - Morgan Stanley)
BUSINESS_SEGMENTS = [
    'institutional securities',
    'wealth management', 
    'investment management',
    'corporate',
    'intersegment eliminations',
    'inter-segment eliminations',
]

# General section headers (more generic)
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

# Patterns that indicate a NEW column header row appearing mid-table
NEW_TABLE_HEADER_PATTERNS = [
    # Period range headers
    'three months ended', 'six months ended', 'nine months ended',
    'twelve months ended', 'year ended', 'fiscal year ended', 'quarter ended',
    
    # Date point headers
    'at march', 'at june', 'at september', 'at december',
    'at january', 'at february', 'at april', 'at may',
    'at july', 'at august', 'at october', 'at november',
    
    # "As of" patterns
    'as of march', 'as of june', 'as of september', 'as of december',
    
    # Generic period patterns
    'for the period', 'for the year', 'for the quarter',
    
    # Normalized period codes (after process step converts to Q-codes)
    # These patterns are needed because process_advanced runs AFTER process step
    'q1-qtd-', 'q2-qtd-', 'q3-qtd-', 'q4-qtd-',  # Quarterly (3-month periods)
    'q1-ytd-', 'q2-ytd-', 'q3-ytd-', 'q4-ytd-',  # Year-to-date periods
    'ytd-20',  # YTD patterns for 10-K reports
]

# Year range for validation (fallback to constants if settings unavailable)
VALID_YEAR_RANGE = (
    getattr(settings, 'EXTRACTION_YEAR_MIN', CONSOLIDATION_YEAR_MIN),
    getattr(settings, 'EXTRACTION_YEAR_MAX', CONSOLIDATION_YEAR_MAX)
)


# =============================================================================
# TABLE CLASSIFICATION PATTERNS
# =============================================================================

UNIT_INDICATORS = [
    'dollars in millions', 'dollars in billions', 'dollars in thousands',
    'in millions', 'in billions', 'in thousands',
    '$ in millions', '$ in billions',
    'in %', 'percentage', 'ratio',
]

TABLE_HEADER_PATTERNS = [
    '$ in millions', '$ in billions', '$ in thousands',
    'three months ended', 'six months ended', 'nine months ended',
    'at june', 'at december', 'at march', 'at september',
    'trading', 'fees', 'net interest', 'total'
]

DATA_LABEL_PATTERNS = [
    'financing', 'execution', 'equity', 'fixed income',
    'common', 'tangible', 'average', 'assets', 'liabilities',
    'revenues', 'expenses', 'income', 'loss'
]

METADATA_BOUNDARY_MARKERS = [
    'row header', 'category (parent)', 'category:', 'line items:',
]


# =============================================================================
# UNIT PATTERNS (from financial_patterns.py)
# =============================================================================

UNIT_PATTERNS: List[str] = [
    '$ in million', '$ in billion', '$ in thousand',
    'in millions', 'in billions', 'in thousands',
    'dollars in millions', 'dollars in billions',
    '(in millions)', '(in billions)', '(in thousands)',
    'amounts in millions', 'amounts in billions',
]

UNIT_PATTERNS_REGEX: Dict[str, List[re.Pattern]] = {
    'millions': [
        re.compile(r'in millions', re.IGNORECASE),
        re.compile(r'\(in millions\)', re.IGNORECASE),
        re.compile(r'\$ millions', re.IGNORECASE),
    ],
    'thousands': [
        re.compile(r'in thousands', re.IGNORECASE),
        re.compile(r'\(in thousands\)', re.IGNORECASE),
        re.compile(r'\$ thousands', re.IGNORECASE),
    ],
    'billions': [
        re.compile(r'in billions', re.IGNORECASE),
        re.compile(r'\(in billions\)', re.IGNORECASE),
        re.compile(r'\$ billions', re.IGNORECASE),
    ],
}


# =============================================================================
# CURRENCY PATTERNS (from financial_patterns.py)
# =============================================================================

CURRENCY_PATTERNS: Dict[str, Dict] = {
    'USD': {'symbols': ['$'], 'codes': ['usd']},
    'EUR': {'symbols': ['€'], 'codes': ['eur']},
    'GBP': {'symbols': ['£'], 'codes': ['gbp']},
}


# =============================================================================
# STATEMENT TYPE KEYWORDS (from financial_patterns.py)
# =============================================================================

STATEMENT_KEYWORDS: Dict[str, List[str]] = {
    'balance_sheet': ['balance sheet', 'financial position', 'assets', 'liabilities'],
    'income_statement': ['income statement', 'operations', 'earnings', 'profit', 'loss'],
    'cash_flow': ['cash flow', 'cash flows'],
    'equity': ['equity', 'stockholders', 'shareholders'],
    'footnotes': ['note', 'footnote'],
}


# =============================================================================
# HELPER FUNCTIONS - Section Detection
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


# =============================================================================
# HELPER FUNCTIONS - Date/Period Detection
# =============================================================================

def is_date_header_row(label: str) -> bool:
    """Check if a row label indicates a date/period header."""
    label_lower = label.lower() if label else ''
    return any(pattern in label_lower for pattern in DATE_HEADER_PATTERNS)


def is_year_value(value: str) -> bool:
    """Check if value is a standalone year within valid range."""
    if isinstance(value, str) and value.isdigit() and len(value) == 4:
        year = int(value)
        return VALID_YEAR_RANGE[0] <= year <= VALID_YEAR_RANGE[1]
    return False


def is_new_table_header_row(row_values: list, first_col_value) -> bool:
    """
    Check if a row represents a NEW column header (indicating table split).
    
    Criteria:
    1. First column is empty OR is a unit indicator ($ in millions, etc.)
    2. Other columns contain date/period patterns
    """
    first_val = str(first_col_value).strip() if first_col_value else ''
    first_val_lower = first_val.lower()
    
    # Empty first column is OK
    is_empty_first_col = not first_val or first_val_lower in ['', 'nan', 'none']
    
    # Unit indicators in first column are also OK (they indicate a new table header)
    is_unit_indicator_first_col = first_val and is_unit_indicator(first_val)
    
    # If first column has content that is NOT a unit indicator, this is not a header row
    if not is_empty_first_col and not is_unit_indicator_first_col:
        return False
    
    # Check if other columns contain date/period patterns
    other_cols_text = ' '.join(str(v) for v in row_values[1:] if v).lower()
    if not other_cols_text:
        return False
    
    return any(pattern in other_cols_text for pattern in NEW_TABLE_HEADER_PATTERNS)


def extract_quarter_from_header(header_text: str) -> str:
    """
    Extract quarter designation from a column header.
    
    Uses centralized MetadataBuilder for consistent quarter detection.
    
    Returns:
        Quarter string (Q1, Q2, Q3, Q4, 3QTD, 6QTD, 9QTD, YTD) or empty string
    """
    from src.utils.metadata_builder import MetadataBuilder
    return MetadataBuilder.extract_quarter_from_header(header_text)


def extract_year_from_header(header_text: str) -> str:
    """
    Extract year from a column header.
    
    Uses centralized MetadataBuilder for consistent year extraction.
    
    Examples:
    - "Three Months Ended March 31, 2024" → "2024"
    - "At June 30, 2023" → "2023"
    """
    from src.utils.metadata_builder import MetadataBuilder
    return MetadataBuilder.extract_year_from_header(header_text)


def is_10k_source(source: str) -> bool:
    """Check if the source is a 10-K annual report."""
    if not source:
        return False
    source_lower = source.lower()
    return '10k' in source_lower or '10-k' in source_lower


def convert_year_to_q4_header(header_text: str, source: str = '') -> str:
    """
    Convert year-only column header to Q4 format for 10-K reports.
    
    For 10-K sources:
    - "2024" → "Q4, 2024"
    
    For 10-Q sources (no change):
    - "2024" → "2024"
    """
    if not header_text:
        return header_text
    
    header_str = str(header_text).strip()
    
    if not is_10k_source(source):
        return header_str
    
    if re.match(r'^20[1-3][0-9]$', header_str):
        return f"Q4, {header_str}"
    
    return header_str


# =============================================================================
# HELPER FUNCTIONS - Unit/Currency Detection (from financial_patterns.py)
# =============================================================================

def is_unit_indicator(text: str) -> bool:
    """
    Check if text is a unit indicator.
    
    Examples: "$ in millions", "(in thousands)"
    """
    if not text:
        return False
    
    text_lower = text.lower().strip()
    
    for pattern in UNIT_PATTERNS:
        if pattern in text_lower:
            return True
    
    if text_lower.startswith('$') and ' in ' in text_lower:
        return True
    
    return False


def detect_units(content: str) -> Optional[str]:
    """
    Detect financial units from content.
    
    Returns:
        Unit type ('millions', 'thousands', 'billions') or None
    """
    if not content:
        return None
    
    content_lower = content.lower()
    
    for unit, patterns in UNIT_PATTERNS_REGEX.items():
        for pattern in patterns:
            if pattern.search(content_lower):
                return unit
    
    return None


def detect_currency(content: str) -> Tuple[str, bool]:
    """
    Detect currency from content.
    
    Returns:
        Tuple of (currency_code, has_currency_indicator)
    """
    if not content:
        return "USD", False
    
    content_lower = content.lower()
    
    for currency, info in CURRENCY_PATTERNS.items():
        for symbol in info['symbols']:
            if symbol in content:
                return currency, True
        
        for code in info['codes']:
            if code in content_lower:
                return currency, True
    
    return "USD", False
