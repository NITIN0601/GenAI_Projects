"""
Quarter Date Mapper - Bidirectional conversion between codes and labels.

Standalone module for Year/Quarter code manipulation.
Used by: process.py, consolidated_exporter.py, table_merger.py, and more.
"""

import re
from typing import Dict


class QuarterDateMapper:
    """
    Bidirectional mapping between standard quarter codes and display labels.
    
    Code Format Examples:
        Q1-2025         → Point-in-time (At March 31, 2025)
        Q1-QTD-2025     → Three Months Ended March 31, 2025
        Q2-QTD-2025     → Three Months Ended June 30, 2025
        Q2-YTD-2025     → Six Months Ended June 30, 2025
        Q3-YTD-2025     → Nine Months Ended September 30, 2025
        YTD-2025        → 2025 (10-K annual report)
    """
    
    # Quarter end dates
    QUARTER_END_DATES = {
        'Q1': ('March', 31),
        'Q2': ('June', 30),
        'Q3': ('September', 30),
        'Q4': ('December', 31),
    }
    
    # Month to quarter mapping
    MONTH_TO_QUARTER = {
        'january': 'Q1', 'february': 'Q1', 'march': 'Q1',
        'april': 'Q2', 'may': 'Q2', 'june': 'Q2',
        'july': 'Q3', 'august': 'Q3', 'september': 'Q3',
        'october': 'Q4', 'november': 'Q4', 'december': 'Q4',
    }
    
    # Period type mappings for YTD
    YTD_MAPPINGS = {
        'Q2-YTD': 'Six Months Ended',
        'Q3-YTD': 'Nine Months Ended',
    }
    
    @classmethod
    def code_to_display(cls, code: str) -> str:
        """
        Convert standard code to display label.
        
        Examples:
            'Q1-2025' → 'At March 31, 2025'
            'Q1-QTD-2025' → 'Three Months Ended March 31, 2025'
            'Q2-YTD-2025' → 'Six Months Ended June 30, 2025'
            'YTD-2025' → '2025'
        """
        if not code:
            return ''
        
        code = str(code).strip()
        
        # Annual (10-K): YTD-2025 → 2025
        if code.startswith('YTD-') and code.count('-') == 1:
            year = code.split('-')[1]
            return year
        
        # Parse code
        parts = code.split('-')
        if len(parts) < 2:
            return code  # Can't parse, return as-is
        
        quarter = parts[0]  # Q1, Q2, Q3, Q4
        year = parts[-1]    # Last part is year
        
        if quarter not in cls.QUARTER_END_DATES:
            return code  # Unknown quarter
        
        month, day = cls.QUARTER_END_DATES[quarter]
        
        # Point-in-time: Q1-2025 → At March 31, 2025
        if len(parts) == 2:
            return f"At {month} {day}, {year}"
        
        # QTD period: Q1-QTD-2025 → Three Months Ended March 31, 2025
        if len(parts) == 3 and parts[1] == 'QTD':
            return f"Three Months Ended {month} {day}, {year}"
        
        # YTD period: Q2-YTD-2025 → Six Months Ended June 30, 2025
        if len(parts) == 3 and parts[1] == 'YTD':
            ytd_key = f"{quarter}-YTD"
            period_type = cls.YTD_MAPPINGS.get(ytd_key, 'Months Ended')
            return f"{period_type} {month} {day}, {year}"
        
        return code  # Can't parse, return as-is
    
    @classmethod
    def display_to_code(cls, display: str, report_type: str = '') -> str:
        """
        Convert display label to standard code.
        
        Examples:
            'At March 31, 2025' → 'Q1-2025'
            'Three Months Ended March 31, 2025' → 'Q1-QTD-2025'
            'Six Months Ended June 30, 2025' → 'Q2-YTD-2025'
            '2025' (10-K) → 'YTD-2025'
        """
        if not display:
            return ''
        
        display_lower = str(display).lower().strip()
        
        # Extract year
        year_match = re.search(r'(20\d{2})', display)
        year = year_match.group(1) if year_match else ''
        
        if not year:
            return display  # Can't parse without year
        
        # Year only (10-K annual): 2025 → YTD-2025
        if re.match(r'^20\d{2}$', display.strip()):
            return f"YTD-{year}"
        
        # Detect quarter from month
        quarter = None
        for month, qtr in cls.MONTH_TO_QUARTER.items():
            if month in display_lower:
                quarter = qtr
                break
        
        if not quarter:
            # Default to Q4 for annual reports
            if '10k' in report_type.lower() or 'annual' in display_lower:
                return f"YTD-{year}"
            return f"Q4-{year}"  # Default
        
        # Detect period type
        if 'nine months' in display_lower or '9 months' in display_lower:
            return f"{quarter}-YTD-{year}"  # Nine Months = YTD
        
        if 'six months' in display_lower or '6 months' in display_lower:
            return f"{quarter}-YTD-{year}"  # Six Months = YTD
        
        if 'three months' in display_lower or '3 months' in display_lower:
            return f"{quarter}-QTD-{year}"  # Three Months = QTD
        
        if display_lower.startswith('at ') or display_lower.startswith('as of '):
            return f"{quarter}-{year}"  # Point-in-time
        
        if 'year ended' in display_lower or 'fiscal year' in display_lower:
            return f"YTD-{year}"  # Annual
        
        # Default: point-in-time
        return f"{quarter}-{year}"
    
    @classmethod
    def normalize_for_merge(cls, header: str, report_type: str = '') -> str:
        """
        Convert column header to standardized merge key.
        
        This is the key used to match columns across different tables/quarters.
        """
        code = cls.display_to_code(header, report_type)
        return code
    
    @classmethod
    def get_merge_key_type(cls, code: str) -> str:
        """
        Determine merge key type from code.
        
        Returns: 'L3_ONLY' (point-in-time, annual) or 'L2_L3' (QTD, YTD periods)
        """
        if not code:
            return 'UNKNOWN'
        
        parts = code.split('-')
        
        # YTD-2025 (annual) → L3 only
        if code.startswith('YTD-') and len(parts) == 2:
            return 'L3_ONLY'
        
        # Q1-2025 (point-in-time) → L3 only
        if len(parts) == 2:
            return 'L3_ONLY'
        
        # Q1-QTD-2025 or Q2-YTD-2025 → L2+L3
        if len(parts) == 3:
            return 'L2_L3'
        
        return 'UNKNOWN'
