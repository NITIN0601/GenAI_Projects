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
    
    # Quarter mapping derived from MONTHS (converts month name to quarter number 1-4)
    # Uses same logic as MetadataBuilder.MONTH_TO_QUARTER but returns int instead of 'Q1'
    MONTH_TO_QUARTER = {
        month: (num - 1) // 3 + 1 
        for month, num in MONTHS.items()
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
        
        Uses MetadataBuilder.convert_to_qn_format with separator.
        
        Examples:
            'March 31, 2025' → 'Q1, 2025'
            'December 31, 2024' → 'Q4, 2024'
            'Three Months Ended June 30, 2024' → '3QTD, 2024'
        
        Returns original header if conversion not possible.
        """
        from src.utils.metadata_builder import MetadataBuilder
        return MetadataBuilder.convert_to_qn_format(header, use_separator=True)
    
    @classmethod
    def get_sort_key(cls, header: str) -> Tuple[int, int, int]:
        """
        Get sort key for header (descending order - newest first).
        
        Returns negative values so sorted() gives newest first.
        """
        year, month, day = cls.parse_date_from_header(header)
        return (-year, -month, -day)
    
    @classmethod
    def get_period_date(cls, year: Optional[int], quarter: Optional[str]) -> str:
        """
        Get standard period end date (YYYY-MM-DD) from year and quarter.
        
        Centralizes logic previously in TableConsolidator._get_period_date.
        
        Args:
            year: Year (e.g., 2025)
            quarter: Quarter string (e.g., 'Q1', 'Q4', '10-K')
            
        Returns:
            Date string in YYYY-MM-DD format
            
        Examples:
            (2025, 'Q1') -> '2025-03-31'
            (2024, 'Q4') -> '2024-12-31'
            (2024, '10-K') -> '2024-12-31'
            (2025, None) -> '2025-12-31'
        """
        if not year:
            return "Unknown"
        
        if not quarter:
            return f"{year}-12-31"
        
        quarter_upper = quarter.upper()
        
        if "Q1" in quarter_upper:
            return f"{year}-03-31"
        elif "Q2" in quarter_upper:
            return f"{year}-06-30"
        elif "Q3" in quarter_upper:
            return f"{year}-09-30"
        elif "Q4" in quarter_upper or "10-K" in quarter_upper or "10K" in quarter_upper:
            return f"{year}-12-31"
        else:
            return f"{year}-12-31"
    
    @classmethod
    def quarter_to_num(cls, quarter: Optional[str]) -> int:
        """
        Convert quarter to number for chronological sorting.
        
        Centralizes logic previously in TableConsolidator._quarter_to_num.
        
        Args:
            quarter: Quarter string (e.g., 'Q1', 'Q4', '10-K')
            
        Returns:
            Integer 1-5 for sorting (Q1=1, Q2=2, Q3=3, Q4/10-K=4, Unknown=5)
        """
        if not quarter:
            return 5
        
        quarter_upper = quarter.upper()
        
        if 'Q1' in quarter_upper:
            return 1
        elif 'Q2' in quarter_upper:
            return 2
        elif 'Q3' in quarter_upper:
            return 3
        elif 'Q4' in quarter_upper or '10K' in quarter_upper or '10-K' in quarter_upper:
            return 4
        return 5
