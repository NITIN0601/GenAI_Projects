"""
Source Parser - Parse metadata from SEC filing filenames.

Extracted from consolidated_exporter.py for reusability.

Handles patterns like:
- 10k1224.pdf → 2024, Q4 (10-K filed Dec 2024)
- 10q0325.pdf → 2025, Q1 (10-Q filed Mar 2025)
"""

import re
from typing import Tuple, Optional
from src.utils import get_logger

logger = get_logger(__name__)


class SourceParser:
    """
    Parse year, quarter, and report type from SEC filing filenames.
    
    Patterns supported:
    - 10k[MM][YY].pdf → Annual report
    - 10q[MM][YY].pdf → Quarterly report
    
    Design: Stateless class methods for horizontal scaling.
    """
    
    # Month to quarter mapping
    MONTH_TO_QUARTER = {
        1: 'Q4',  # Jan filing = Q4 of previous year
        2: 'Q4',  # Feb filing = Q4 of previous year
        3: 'Q1',  # Mar filing = Q1
        6: 'Q2',  # Jun filing = Q2
        9: 'Q3',  # Sep filing = Q3
        12: 'Q4', # Dec filing = Q4
    }
    
    @classmethod
    def parse_year_quarter(cls, source: str) -> Tuple[str, str]:
        """
        Parse year and quarter from source filename.
        
        Args:
            source: Source filename (e.g., '10k1224.pdf')
            
        Returns:
            Tuple of (year, quarter) e.g., ('2024', 'Q4')
        """
        match = re.search(r'(10[kq])(\d{2})(\d{2})', source.lower())
        if match:
            report_type = match.group(1)
            month = int(match.group(2))
            year = 2000 + int(match.group(3))
            
            if report_type == '10k':
                return str(year), 'Q4'
            else:
                # Handle edge cases
                if month in [1, 2]:
                    year -= 1
                quarter = cls.MONTH_TO_QUARTER.get(month, f'Q{(month-1)//3 + 1}')
                return str(year), quarter
        
        return '', ''
    
    @classmethod
    def parse_report_type(cls, source: str) -> str:
        """
        Detect report type from source filename.
        
        Returns:
            '10-K', '10-Q', or 'UNKNOWN'
        """
        source_lower = source.lower()
        if '10k' in source_lower:
            return '10-K'
        elif '10q' in source_lower:
            return '10-Q'
        return 'UNKNOWN'
    
    @classmethod
    def is_annual_report(cls, source: str) -> bool:
        """Check if source is an annual report (10-K)."""
        return cls.parse_report_type(source) == '10-K'
    
    @classmethod
    def is_quarterly_report(cls, source: str) -> bool:
        """Check if source is a quarterly report (10-Q)."""
        return cls.parse_report_type(source) == '10-Q'
    
    @classmethod
    def get_sort_key(cls, source: str) -> Tuple[int, int]:
        """
        Get sort key for chronological ordering.
        
        Returns:
            Tuple of (year, quarter_num) for sorting
        """
        year, quarter = cls.parse_year_quarter(source)
        year_int = int(year) if year else 0
        quarter_int = int(quarter[1]) if quarter and quarter.startswith('Q') else 0
        return (year_int, quarter_int)


__all__ = ['SourceParser']
