"""
Header Normalizer Module - Single Source of Truth.

Consolidates all header normalization logic for financial date headers.
Imported and used by: step.py, excel_exporter.py, consolidated_exporter.py, metadata_builder.py

Key Functions:
- normalize_point_in_time_header: Full text → Qn-QTD-YYYY format
- convert_year_to_period: Bare years → YTD/Qn-YYYY based on source type
- combine_category_with_period: Category + normalized period → combined header
- extract_quarter_from_header: Extract quarter part (Q1-QTD, Q2-YTD, etc.)
- extract_year_from_header: Extract year (2024, 2025, etc.)
"""

import re
from typing import Optional, List, Dict, Tuple


__all__ = [
    'HeaderNormalizer',
    'MONTH_TO_QUARTER_MAP',
    'normalize_point_in_time_header',
    'convert_year_to_period',
    'combine_category_with_period',
    'extract_quarter_from_header',
    'extract_year_from_header',
    'is_10k_source',
    'is_valid_date_code',
]


# =============================================================================
# MONTH TO QUARTER MAPPINGS - Single Source of Truth
# =============================================================================

# Full and abbreviated month names to quarter mapping
MONTH_TO_QUARTER_MAP = {
    # Full names
    'january': 'Q1', 'february': 'Q1', 'march': 'Q1',
    'april': 'Q2', 'may': 'Q2', 'june': 'Q2',
    'july': 'Q3', 'august': 'Q3', 'september': 'Q3',
    'october': 'Q4', 'november': 'Q4', 'december': 'Q4',
    # Abbreviations
    'jan': 'Q1', 'feb': 'Q1', 'mar': 'Q1',
    'apr': 'Q2', 'jun': 'Q2',
    'jul': 'Q3', 'aug': 'Q3', 'sept': 'Q3', 'sep': 'Q3',
    'oct': 'Q4', 'nov': 'Q4', 'dec': 'Q4',
}

# Period type detection patterns
PERIOD_TYPE_PATTERNS = {
    'QTD3': ['three months ended', '3 months ended', 'three-month', '3-month'],
    'QTD6': ['six months ended', '6 months ended', 'six-month', '6-month'],
    'QTD9': ['nine months ended', '9 months ended', 'nine-month', '9-month'],
    'YTD': ['year ended', 'fiscal year ended', 'twelve months ended', 'annual'],
}


# =============================================================================
# CORE NORMALIZATION FUNCTIONS
# =============================================================================

def normalize_point_in_time_header(value: str) -> Optional[str]:
    """
    Normalize various date header formats to standardized Qn-YYYY or Qn-QTD-YYYY codes.
    
    This is the PRIMARY normalization function - converts full text dates to codes.
    
    Handles:
    - "At June 30, 2024" → "Q2-2024"
    - "As of December 31, 2024" → "Q4-2024"
    - "Three Months Ended June 30, 2024" → "Q2-QTD-2024"
    - "Six Months Ended June 30, 2024" → "Q2-YTD-2024"
    - "Nine Months Ended September 30, 2024" → "Q3-YTD-2024"
    - "Year Ended December 31, 2024" → "YTD-2024"
    - "Q1,2025" → "Q1-2025" (comma format)
    - "Q3-QTD-2025" → "Q3-QTD-2025" (already normalized)
    
    Args:
        value: Header string to normalize
        
    Returns:
        Normalized code (e.g., "Q2-QTD-2024", "YTD-2024") or None if not recognized
    """
    if not value:
        return None
    
    val_str = str(value).strip()
    val_lower = val_str.lower()
    
    # Pattern 1: Comma format - "Q1,2025" or "YTD,2024"
    comma_match = re.match(r'^(Q[1-4]|YTD)\s*,\s*(20\d{2})$', val_str, re.IGNORECASE)
    if comma_match:
        prefix = comma_match.group(1).upper()
        year = comma_match.group(2)
        return f"{prefix}-{year}"
    
    # Pattern 2: Already correct format - "Q1-2025", "YTD-2024", "Q3-QTD-2025", "Q2-YTD-2024"
    if re.match(r'^Q[1-4]-20\d{2}$', val_str, re.IGNORECASE):
        return val_str.upper()
    if re.match(r'^YTD-20\d{2}$', val_str, re.IGNORECASE):
        return val_str.upper()
    if re.match(r'^Q[1-4]-(QTD|YTD)-20\d{2}$', val_str, re.IGNORECASE):
        return val_str.upper()
    
    # Extract year - needed for remaining patterns
    year_match = re.search(r'(20\d{2})', val_str)
    if not year_match:
        return None
    year = year_match.group(1)
    
    # Find month in the value
    detected_month = None
    for month_name in MONTH_TO_QUARTER_MAP:
        if month_name in val_lower:
            detected_month = month_name
            break
    
    if not detected_month:
        # Pattern for "Year Ended" without specific month (annual = YTD)
        if 'year ended' in val_lower or 'fiscal year' in val_lower:
            return f"YTD-{year}"
        return None
    
    quarter = MONTH_TO_QUARTER_MAP[detected_month]
    
    # Pattern 3: "At" or "As of" prefixed - point-in-time
    if val_lower.startswith('at ') or 'as of ' in val_lower:
        return f"{quarter}-{year}"
    
    # Pattern 4: "Three Months Ended" - quarterly period (QTD)
    if 'three months ended' in val_lower or '3 months ended' in val_lower:
        return f"{quarter}-QTD-{year}"
    
    # Pattern 5: "Six Months Ended" - YTD for Q2
    if 'six months ended' in val_lower or '6 months ended' in val_lower:
        return f"{quarter}-YTD-{year}"
    
    # Pattern 6: "Nine Months Ended" - YTD for Q3
    if 'nine months ended' in val_lower or '9 months ended' in val_lower:
        return f"{quarter}-YTD-{year}"
    
    # Pattern 7: "Year Ended" or "Twelve Months Ended" - annual = YTD
    if 'year ended' in val_lower or 'twelve months ended' in val_lower:
        return f"YTD-{year}"
    
    # Pattern 8: "For the X Months Ended" format
    if 'for the three months' in val_lower:
        return f"{quarter}-QTD-{year}"
    if 'for the six months' in val_lower:
        return f"{quarter}-YTD-{year}"
    if 'for the nine months' in val_lower:
        return f"{quarter}-YTD-{year}"
    
    # Pattern 9: Just month and year (e.g., "December 31, 2024")
    # Only if it looks like a date header
    if re.search(r'(january|february|march|april|may|june|july|august|september|october|november|december|jan|feb|mar|apr|jun|jul|aug|sept|sep|oct|nov|dec)\s+\d{1,2}', val_lower):
        return f"{quarter}-{year}"
    
    return None


def is_10k_source(source: str) -> bool:
    """Check if the source is a 10-K annual report."""
    if not source:
        return False
    source_lower = source.lower()
    return '10k' in source_lower or '10-k' in source_lower


def convert_year_to_period(year: str, source: str = '') -> str:
    """
    Convert bare year to period code based on source type.
    
    For 10-K sources:
    - "2024" → "YTD-2024" (10-K are annual = full year = YTD)
    
    For 10-Q sources (derive quarter from filename):
    - "2024" from 10q0624 → "Q2-2024" (June = Q2)
    - "2024" from 10q0325 → "Q1-2024" (March = Q1)
    - "2025" from 10q0925 → "Q3-2025" (Sept = Q3)
    
    Args:
        year: Year string (e.g., "2024")
        source: Source filename for context
        
    Returns:
        Period code (e.g., "YTD-2024", "Q2-2024") or original year
    """
    if not year:
        return year
    
    year_str = str(year).strip()
    
    # Only process 4-digit year strings
    if not re.match(r'^20[1-3][0-9]$', year_str):
        return year_str
    
    source_lower = source.lower() if source else ''
    
    # 10-K: Annual report = Full Year = YTD
    if is_10k_source(source):
        return f"YTD-{year_str}"
    
    # 10-Q: Derive quarter from filename (10q0624 = June = Q2)
    if '10q' in source_lower:
        month_to_quarter = {
            '03': 'Q1', '0325': 'Q1', '0324': 'Q1',  # March
            '06': 'Q2', '0624': 'Q2', '0625': 'Q2',  # June
            '09': 'Q3', '0924': 'Q3', '0925': 'Q3',  # September
            '12': 'Q4', '1224': 'Q4', '1225': 'Q4',  # December
        }
        for pattern, quarter in month_to_quarter.items():
            if pattern in source_lower:
                return f"{quarter}-{year_str}"
    
    return year_str


def combine_category_with_period(
    categories: List[str], 
    periods: List[str]
) -> Tuple[List[str], List[str]]:
    """
    Combine category labels (L0) with normalized periods (L1).
    
    Example:
        categories = ['Average Daily Balance']
        periods = ['Q4-QTD-2024', 'Q3-QTD-2024']
        
        Returns:
            ([], ['Average Daily Balance Q4-QTD-2024', 'Average Daily Balance Q3-QTD-2024'])
    
    Args:
        categories: List of category labels (e.g., ['Average Daily Balance'])
        periods: List of normalized period codes (e.g., ['Q4-QTD-2024'])
        
    Returns:
        Tuple of (updated_categories, updated_periods)
    """
    if not categories or not periods:
        return categories, periods
    
    combined_headers = []
    
    for category in categories:
        cat_str = str(category).strip()
        # Check if category is NOT a date pattern
        is_category = not any(p in cat_str.lower() for p in 
            ['months ended', 'at ', 'as of ', 'q1-', 'q2-', 'q3-', 'q4-', 'ytd-', 'qtd-'])
        
        if is_category and cat_str:
            for period in periods:
                period_str = str(period).strip()
                # Check if period is a normalized code (Qn-YYYY or Qn-QTD-YYYY format)
                if re.match(r'^Q[1-4]-(QTD|YTD)?-?20\d{2}$', period_str) or re.match(r'^YTD-20\d{2}$', period_str):
                    combined = f"{cat_str} {period_str}"
                    if combined not in combined_headers:
                        combined_headers.append(combined)
                else:
                    if period_str not in combined_headers:
                        combined_headers.append(period_str)
    
    if combined_headers:
        return [], combined_headers
    return categories, periods


def combine_period_with_dates(
    period_types: List[str],
    dates: List[str]
) -> List[str]:
    """
    Combine period type headers (L1) with date headers (L2) and normalize.
    
    Example:
        period_types = ['Three Months Ended']
        dates = ['December 31, 2024', 'September 30, 2024']
        
        Returns:
            ['Q4-QTD-2024', 'Q3-QTD-2024']
    
    Args:
        period_types: List of period type headers (e.g., ['Three Months Ended'])
        dates: List of date headers (e.g., ['December 31, 2024'])
        
    Returns:
        List of normalized period codes
    """
    normalized = []
    
    for period_type in period_types:
        period_str = str(period_type).strip()
        has_period = any(p in period_str.lower() for p in ['months ended', 'at ', 'as of '])
        has_year = bool(re.search(r'20\d{2}', period_str))
        
        if has_period and not has_year and dates:
            for date in dates:
                date_str = str(date).strip()
                # Year-only
                if re.match(r'^20\d{2}$', date_str):
                    combined = f"{period_str.rstrip(',')} {date_str}"
                    norm = normalize_point_in_time_header(combined)
                    if norm and norm not in normalized:
                        normalized.append(norm)
                # Full date (e.g., "December 31, 2024")
                elif re.search(r'(january|february|march|april|may|june|july|august|september|october|november|december|jan|feb|mar|apr|jun|jul|aug|sept|sep|oct|nov|dec)', date_str.lower()) and re.search(r'20\d{2}', date_str):
                    combined = f"{period_str.rstrip(',')} {date_str}"
                    norm = normalize_point_in_time_header(combined)
                    if norm and norm not in normalized:
                        normalized.append(norm)
        elif has_period and has_year:
            norm = normalize_point_in_time_header(period_str)
            if norm and norm not in normalized:
                normalized.append(norm)
        else:
            if period_str and period_str not in normalized:
                normalized.append(period_str)
    
    return normalized if normalized else period_types


def extract_quarter_from_header(header: str) -> str:
    """
    Extract quarter code from header (Q1, Q2, Q3, Q4, Q1-QTD, Q2-YTD, etc).
    
    Examples:
        'Three Months Ended June 30, 2024' → 'Q2-QTD'
        'Six Months Ended June 30, 2024' → 'Q2-YTD'
        'At December 31, 2024' → 'Q4'
        'Year Ended December 31, 2024' → 'YTD'
    
    Args:
        header: Column header string
        
    Returns:
        Quarter code (e.g., 'Q2-QTD', 'YTD') or empty string
    """
    if not header:
        return ''
    
    header_lower = str(header).lower()
    
    # Already normalized format (Q2-QTD-2024 → Q2-QTD)
    match = re.match(r'^(Q[1-4](?:-(?:QTD|YTD))?)-20\d{2}$', str(header), re.IGNORECASE)
    if match:
        return match.group(1).upper()
    
    # YTD-2024 → YTD
    if re.match(r'^YTD-20\d{2}$', str(header), re.IGNORECASE):
        return 'YTD'
    
    # Detect period type
    period_suffix = ''
    if 'three months ended' in header_lower or '3 months ended' in header_lower:
        period_suffix = '-QTD'
    elif 'six months ended' in header_lower or '6 months ended' in header_lower:
        period_suffix = '-YTD'
    elif 'nine months ended' in header_lower or '9 months ended' in header_lower:
        period_suffix = '-YTD'
    elif 'year ended' in header_lower or 'fiscal year' in header_lower:
        return 'YTD'
    
    # Find quarter from month
    for month_name, quarter in MONTH_TO_QUARTER_MAP.items():
        if month_name in header_lower:
            return f"{quarter}{period_suffix}"
    
    return ''


def extract_year_from_header(header: str) -> str:
    """
    Extract year from header.
    
    Examples:
        'Three Months Ended June 30, 2024' → '2024'
        'Q2-QTD-2024' → '2024'
        'At December 31, 2025' → '2025'
    
    Args:
        header: Column header string
        
    Returns:
        Year string (e.g., '2024') or empty string
    """
    if not header:
        return ''
    
    match = re.search(r'(20\d{2})', str(header))
    return match.group(1) if match else ''


def is_valid_date_code(code: str) -> bool:
    """
    Check if a string is a valid normalized date code.
    
    Valid formats:
    - Q1-2024, Q2-2024, Q3-2024, Q4-2024
    - Q1-QTD-2024, Q2-QTD-2024, Q3-QTD-2024, Q4-QTD-2024
    - Q1-YTD-2024, Q2-YTD-2024, Q3-YTD-2024, Q4-YTD-2024
    - YTD-2024
    """
    if not code:
        return False
    
    pattern = re.compile(r'^(Q[1-4](-QTD|-YTD)?|YTD)-20\d{2}$', re.IGNORECASE)
    return bool(pattern.match(str(code).strip()))


# =============================================================================
# HEADER NORMALIZER CLASS - OOP Interface
# =============================================================================

class HeaderNormalizer:
    """
    Object-oriented interface for header normalization.
    
    Provides class methods that wrap the module-level functions.
    """
    
    MONTH_TO_QUARTER = MONTH_TO_QUARTER_MAP
    
    @classmethod
    def normalize(cls, value: str) -> Optional[str]:
        """Normalize a header value."""
        return normalize_point_in_time_header(value)
    
    @classmethod
    def convert_year(cls, year: str, source: str = '') -> str:
        """Convert bare year to period code."""
        return convert_year_to_period(year, source)
    
    @classmethod
    def combine_category(cls, categories: List[str], periods: List[str]) -> Tuple[List[str], List[str]]:
        """Combine categories with periods."""
        return combine_category_with_period(categories, periods)
    
    @classmethod
    def combine_periods(cls, period_types: List[str], dates: List[str]) -> List[str]:
        """Combine period types with dates."""
        return combine_period_with_dates(period_types, dates)
    
    @classmethod
    def extract_quarter(cls, header: str) -> str:
        """Extract quarter from header."""
        return extract_quarter_from_header(header)
    
    @classmethod
    def extract_year(cls, header: str) -> str:
        """Extract year from header."""
        return extract_year_from_header(header)
    
    @classmethod
    def is_valid_code(cls, code: str) -> bool:
        """Check if code is valid."""
        return is_valid_date_code(code)
    
    @classmethod
    def is_10k(cls, source: str) -> bool:
        """Check if source is 10-K."""
        return is_10k_source(source)
