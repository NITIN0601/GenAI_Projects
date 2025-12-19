"""
Date Utilities for Excel Export.

Handles date parsing, formatting, and quarter conversion for consolidated reports.
"""

import re
from typing import Tuple, Optional


class DateUtils:
    """Utilities for date parsing and formatting in financial reports."""
    
    # Month name to number mapping
    MONTHS = {
        'january': 1, 'jan': 1,
        'february': 2, 'feb': 2,
        'march': 3, 'mar': 3,
        'april': 4, 'apr': 4,
        'may': 5,
        'june': 6, 'jun': 6,
        'july': 7, 'jul': 7,
        'august': 8, 'aug': 8,
        'september': 9, 'sep': 9,
        'october': 10, 'oct': 10,
        'november': 11, 'nov': 11,
        'december': 12, 'dec': 12
    }
    
    # Month to fiscal quarter mapping (standard calendar)
    MONTH_TO_QUARTER = {
        'january': 1, 'jan': 1, 'february': 1, 'feb': 1, 'march': 1, 'mar': 1,
        'april': 2, 'apr': 2, 'may': 2, 'june': 2, 'jun': 2,
        'july': 3, 'jul': 3, 'august': 3, 'aug': 3, 'september': 3, 'sep': 3,
        'october': 4, 'oct': 4, 'november': 4, 'nov': 4, 'december': 4, 'dec': 4
    }
    
    # Prefixes to remove from date headers
    DATE_PREFIXES = [
        r'three\s+months?\s+ended\s*', r'six\s+months?\s+ended\s*',
        r'nine\s+months?\s+ended\s*', r'twelve\s+months?\s+ended\s*',
        r'year\s+ended\s*', r'quarter\s+ended\s*', r'period\s+ended\s*',
        r'ended\s+', r'^at\s+', r'^as\s+of\s+',
    ]
    
    @classmethod
    def parse_date_from_header(cls, header: str) -> Tuple[int, int, int]:
        """
        Parse date from column header for sorting.
        
        Returns:
            Tuple of (year, month, day) for sorting
        """
        header_lower = header.lower()
        
        # Extract year
        year_match = re.search(r'20\d{2}', header)
        year = int(year_match.group()) if year_match else 9999
        
        # Extract month
        month = 0
        for month_name, month_num in cls.MONTHS.items():
            if month_name in header_lower:
                month = month_num
                break
        
        # Extract day
        day_match = re.search(r'\b(\d{1,2})\b', header)
        day = int(day_match.group(1)) if day_match and 1 <= int(day_match.group(1)) <= 31 else 0
        
        return (year, month, day)
    
    @classmethod
    def extract_date_from_header(cls, header: str) -> str:
        """
        Extract just the date portion from a header.
        
        Removes prefixes like "Three Months Ended", "Year Ended", etc.
        """
        result = header
        
        for prefix in cls.DATE_PREFIXES:
            result = re.sub(prefix, '', result, flags=re.IGNORECASE)
        
        result = re.sub(r'\s+', ' ', result).strip()
        result = re.sub(r'^,\s*', '', result)
        
        return result if result else header
    
    @classmethod
    def convert_to_quarter_format(cls, header: str) -> str:
        """
        Convert date-based column header to Qn, YYYY format.
        
        Examples:
            'March 31, 2025' → 'Q1, 2025'
            'December 31, 2024' → 'Q4, 2024'
            'June 30, 2024' → 'Q2, 2024'
            'September 30, 2024' → 'Q3, 2024'
        
        Returns original header if conversion not possible.
        """
        header_lower = header.lower()
        
        # Extract year
        year_match = re.search(r'(20\d{2})', header)
        if not year_match:
            return header
        year = year_match.group(1)
        
        # Find quarter based on month
        quarter = None
        for month_name, q in cls.MONTH_TO_QUARTER.items():
            if month_name in header_lower:
                quarter = q
                break
        
        if quarter:
            return f"Q{quarter}, {year}"
        
        return header
    
    @classmethod
    def get_sort_key(cls, header: str) -> Tuple[int, int, int]:
        """
        Get sort key for header (descending order - newest first).
        
        Returns negative values so sorted() gives newest first.
        """
        year, month, day = cls.parse_date_from_header(header)
        return (-year, -month, -day)


# Convenience functions for backward compatibility
def parse_date_from_header(header: str) -> Tuple[int, int, int]:
    """Parse date from column header for sorting."""
    return DateUtils.parse_date_from_header(header)


def convert_to_quarter_format(header: str) -> str:
    """Convert date header to Q1, 2025 format."""
    return DateUtils.convert_to_quarter_format(header)
