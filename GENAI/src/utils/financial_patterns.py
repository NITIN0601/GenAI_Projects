"""
Centralized financial patterns and constants.

Consolidates patterns used across extraction, formatting, and enrichment modules.
This avoids duplication and ensures consistent detection across the codebase.
"""

import re
from typing import List, Dict, Set

__all__ = [
    'UNIT_PATTERNS',
    'UNIT_PATTERNS_REGEX',
    'CURRENCY_PATTERNS',
    'STATEMENT_KEYWORDS',
    'is_unit_indicator',
    'detect_units',
    'detect_currency',
]


# =============================================================================
# UNIT PATTERNS
# =============================================================================

# String-based unit patterns for simple string matching (case-insensitive)
UNIT_PATTERNS: List[str] = [
    '$ in million',
    '$ in billion', 
    '$ in thousand',
    'in millions',
    'in billions',
    'in thousands',
    'dollars in millions',
    'dollars in billions',
    '(in millions)',
    '(in billions)',
    '(in thousands)',
    'amounts in millions',
    'amounts in billions',
]

# Regex-based patterns for more precise matching
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
# CURRENCY PATTERNS
# =============================================================================

CURRENCY_PATTERNS: Dict[str, Dict] = {
    'USD': {
        'symbols': ['$'],
        'codes': ['usd'],
    },
    'EUR': {
        'symbols': ['€'],
        'codes': ['eur'],
    },
    'GBP': {
        'symbols': ['£'],
        'codes': ['gbp'],
    },
}


# =============================================================================
# STATEMENT TYPE KEYWORDS
# =============================================================================

STATEMENT_KEYWORDS: Dict[str, List[str]] = {
    'balance_sheet': ['balance sheet', 'financial position', 'assets', 'liabilities'],
    'income_statement': ['income statement', 'operations', 'earnings', 'profit', 'loss'],
    'cash_flow': ['cash flow', 'cash flows'],
    'equity': ['equity', 'stockholders', 'shareholders'],
    'footnotes': ['note', 'footnote'],
}


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def is_unit_indicator(text: str) -> bool:
    """
    Check if text is a unit indicator.
    
    Examples: "$ in millions", "(in thousands)", "amounts in billions"
    
    Args:
        text: Text to check
        
    Returns:
        True if text contains unit indicator pattern
    """
    if not text:
        return False
    
    text_lower = text.lower().strip()
    
    # Check string patterns
    for pattern in UNIT_PATTERNS:
        if pattern in text_lower:
            return True
    
    # Also check if it starts with $ and contains 'in'
    if text_lower.startswith('$') and ' in ' in text_lower:
        return True
    
    return False


def detect_units(content: str) -> str:
    """
    Detect financial units from content.
    
    Args:
        content: Content to analyze
        
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


def detect_currency(content: str) -> tuple:
    """
    Detect currency from content.
    
    Args:
        content: Content to analyze
        
    Returns:
        Tuple of (currency_code, has_currency_indicator)
    """
    if not content:
        return "USD", False
    
    content_lower = content.lower()
    
    for currency, info in CURRENCY_PATTERNS.items():
        # Check symbols
        for symbol in info['symbols']:
            if symbol in content:
                return currency, True
        
        # Check codes
        for code in info['codes']:
            if code in content_lower:
                return currency, True
    
    # Default to USD (common in financial documents)
    return "USD", False
