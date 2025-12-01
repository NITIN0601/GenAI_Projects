"""Parse and standardize period information from table headers."""

import re
from datetime import datetime
from typing import Optional
from dateutil.parser import parse as parse_date

from models.enhanced_schemas import Period


class PeriodParser:
    """
    Parse and standardize period information from table headers.
    
    Handles various date formats found in financial reports:
    - "Three Months Ended March 31, 2025"
    - "Quarter Ended June 30, 2024"
    - "At March 31, 2025"
    - "As of December 31, 2024"
    - "Q1 2025"
    - "2025 Q1"
    """
    
    # Regex patterns for different period formats
    PATTERNS = [
        # "Three Months Ended March 31, 2025"
        (r'Three Months Ended\s+(\w+\s+\d{1,2},?\s+\d{4})', 'quarter_ended'),
        # "Quarter Ended June 30, 2024"
        (r'Quarter Ended\s+(\w+\s+\d{1,2},?\s+\d{4})', 'quarter_ended'),
        # "At March 31, 2025"
        (r'At\s+(\w+\s+\d{1,2},?\s+\d{4})', 'point_in_time'),
        # "As of December 31, 2024"
        (r'As of\s+(\w+\s+\d{1,2},?\s+\d{4})', 'point_in_time'),
        # "Q1 2025" or "Q1 '25"
        (r'Q([1-4])\s+[\'"]?(\d{2,4})', 'quarter_short'),
        # "2025 Q1"
        (r'(\d{4})\s+Q([1-4])', 'quarter_short_reverse'),
        # "Year Ended December 31, 2024"
        (r'Year Ended\s+(\w+\s+\d{1,2},?\s+\d{4})', 'year_ended'),
        # "For the year ended..."
        (r'For the year ended\s+(\w+\s+\d{1,2},?\s+\d{4})', 'year_ended'),
    ]
    
    # Quarter end months
    QUARTER_END_MONTHS = {
        1: 3,   # Q1 ends in March
        2: 6,   # Q2 ends in June
        3: 9,   # Q3 ends in September
        4: 12   # Q4 ends in December
    }
    
    def parse_period(self, header_text: str) -> Optional[Period]:
        """
        Parse period from header text and create standardized Period object.
        
        Args:
            header_text: Column header text
        
        Returns:
            Period object or None if no period found
        """
        for pattern, period_format in self.PATTERNS:
            match = re.search(pattern, header_text, re.IGNORECASE)
            if match:
                return self._create_period_from_match(match, period_format)
        
        return None
    
    def _create_period_from_match(self, match, period_format: str) -> Period:
        """Create Period object from regex match."""
        
        if period_format == 'quarter_ended':
            # Parse date from "March 31, 2025"
            date_str = match.group(1)
            end_date = parse_date(date_str)
            
            # Determine quarter from month
            quarter = (end_date.month - 1) // 3 + 1
            
            # Calculate start date
            start_month = (quarter - 1) * 3 + 1
            start_date = end_date.replace(month=start_month, day=1)
            
            return Period(
                period_type='quarter',
                year=end_date.year,
                quarter=quarter,
                start_date=start_date.isoformat(),
                end_date=end_date.isoformat(),
                display_label=f'Q{quarter} {end_date.year}'
            )
        
        elif period_format == 'point_in_time':
            # "At March 31, 2025" - point in time (balance sheet date)
            date_str = match.group(1)
            date = parse_date(date_str)
            
            quarter = (date.month - 1) // 3 + 1
            
            return Period(
                period_type='point_in_time',
                year=date.year,
                quarter=quarter,
                start_date=None,
                end_date=date.isoformat(),
                display_label=f'{date.strftime("%b %d, %Y")}'
            )
        
        elif period_format == 'quarter_short':
            # "Q1 2025"
            quarter = int(match.group(1))
            year_str = match.group(2)
            
            # Handle 2-digit year
            if len(year_str) == 2:
                year = 2000 + int(year_str)
            else:
                year = int(year_str)
            
            # Calculate dates
            end_month = self.QUARTER_END_MONTHS[quarter]
            end_date = datetime(year, end_month, self._last_day_of_month(year, end_month))
            
            start_month = (quarter - 1) * 3 + 1
            start_date = datetime(year, start_month, 1)
            
            return Period(
                period_type='quarter',
                year=year,
                quarter=quarter,
                start_date=start_date.isoformat(),
                end_date=end_date.isoformat(),
                display_label=f'Q{quarter} {year}'
            )
        
        elif period_format == 'quarter_short_reverse':
            # "2025 Q1"
            year = int(match.group(1))
            quarter = int(match.group(2))
            
            end_month = self.QUARTER_END_MONTHS[quarter]
            end_date = datetime(year, end_month, self._last_day_of_month(year, end_month))
            
            start_month = (quarter - 1) * 3 + 1
            start_date = datetime(year, start_month, 1)
            
            return Period(
                period_type='quarter',
                year=year,
                quarter=quarter,
                start_date=start_date.isoformat(),
                end_date=end_date.isoformat(),
                display_label=f'Q{quarter} {year}'
            )
        
        elif period_format == 'year_ended':
            # "Year Ended December 31, 2024"
            date_str = match.group(1)
            end_date = parse_date(date_str)
            
            start_date = datetime(end_date.year, 1, 1)
            
            return Period(
                period_type='year',
                year=end_date.year,
                quarter=None,
                start_date=start_date.isoformat(),
                end_date=end_date.isoformat(),
                display_label=f'{end_date.year}'
            )
        
        return None
    
    def _last_day_of_month(self, year: int, month: int) -> int:
        """Get last day of month."""
        if month == 12:
            next_month = datetime(year + 1, 1, 1)
        else:
            next_month = datetime(year, month + 1, 1)
        
        last_day = next_month - datetime.resolution
        return last_day.day
    
    def compare_periods(self, period1: Period, period2: Period) -> str:
        """
        Compare two periods and return relationship.
        
        Returns: 'same', 'sequential', 'yoy' (year-over-year), 'different'
        """
        if period1.year == period2.year and period1.quarter == period2.quarter:
            return 'same'
        
        # Check if sequential quarters
        if period1.quarter and period2.quarter:
            if period1.year == period2.year:
                if abs(period1.quarter - period2.quarter) == 1:
                    return 'sequential'
            elif abs(period1.year - period2.year) == 1:
                # Check if Q4 -> Q1 transition
                if (period1.quarter == 4 and period2.quarter == 1) or \
                   (period1.quarter == 1 and period2.quarter == 4):
                    return 'sequential'
        
        # Check year-over-year
        if period1.quarter == period2.quarter and abs(period1.year - period2.year) == 1:
            return 'yoy'
        
        return 'different'


# Global parser instance
_parser: Optional[PeriodParser] = None


def get_period_parser() -> PeriodParser:
    """Get or create global period parser instance."""
    global _parser
    if _parser is None:
        _parser = PeriodParser()
    return _parser
