"""
Filing calendar for Morgan Stanley SEC filings.

Predicts when quarterly and annual reports will be available based on historical patterns.
"""

from datetime import datetime, timedelta
from typing import List, Dict
import logging

logger = logging.getLogger(__name__)

try:
    import holidays
    HOLIDAYS_AVAILABLE = True
except ImportError:
    HOLIDAYS_AVAILABLE = False
    logger.warning("holidays package not available - weekend/holiday adjustments disabled")


class FilingCalendar:
    """
    Predict Morgan Stanley filing dates based on historical patterns.
    
    Filing Schedule:
    - Q1 (Jan-Mar): Filed early-mid May (~45 days after quarter end)
    - Q2 (Apr-Jun): Filed early-mid August
    - Q3 (Jul-Sep): Filed early-mid November
    - 10-K (Oct-Dec): Filed late February (~60 days after year end)
    
    Historical Data:
    - Q1: May 5-15
    - Q2: Aug 5-15
    - Q3: Nov 5-15
    - 10-K: Feb 20-28
    """
    
    # Filing windows based on historical analysis
    FILING_WINDOWS = {
        "Q1": {"month": 5, "day_range": (5, 15), "name": "Q1 2025 (10-Q)"},
        "Q2": {"month": 8, "day_range": (5, 15), "name": "Q2 2025 (10-Q)"},
        "Q3": {"month": 11, "day_range": (5, 15), "name": "Q3 2025 (10-Q)"},
        "10K": {"month": 2, "day_range": (20, 28), "name": "Annual Report (10-K)"}
    }
    
    # Month codes for download script
    QUARTER_TO_MONTH = {
        "Q1": "03",
        "Q2": "06",
        "Q3": "09",
        "10K": "12"
    }
    
    def __init__(self):
        """Initialize filing calendar."""
        if HOLIDAYS_AVAILABLE:
            self.us_holidays = holidays.US()
        else:
            self.us_holidays = set()
    
    def predict_filing_date(self, year: int, quarter: str) -> datetime:
        """
        Predict when a filing will be available.
        
        Args:
            year: Year of the report
            quarter: "Q1", "Q2", "Q3", or "10K"
            
        Returns:
            Predicted filing date
        """
        if quarter not in self.FILING_WINDOWS:
            raise ValueError(f"Invalid quarter: {quarter}. Must be Q1, Q2, Q3, or 10K")
        
        window = self.FILING_WINDOWS[quarter]
        
        # For 10-K, the filing is in the FOLLOWING year
        filing_year = year + 1 if quarter == "10K" else year
        
        # Start with middle of the window
        day_start, day_end = window["day_range"]
        target_day = (day_start + day_end) // 2
        
        target_date = datetime(filing_year, window["month"], target_day)
        
        # Adjust for weekends and holidays
        target_date = self._adjust_for_business_day(target_date)
        
        return target_date
    
    def _adjust_for_business_day(self, date: datetime) -> datetime:
        """Adjust date to next business day if it falls on weekend/holiday."""
        # Move forward if weekend or holiday
        while date.weekday() >= 5 or date in self.us_holidays:
            date += timedelta(days=1)
        
        return date
    
    def get_upcoming_filings(self, days_ahead: int = 90) -> List[Dict]:
        """
        Get list of upcoming filings in the next N days.
        
        Args:
            days_ahead: Number of days to look ahead
            
        Returns:
            List of filing info dictionaries
        """
        today = datetime.now()
        upcoming = []
        
        # Check filings for current and next year
        for year in [today.year, today.year + 1]:
            for quarter in ["Q1", "Q2", "Q3", "10K"]:
                try:
                    filing_date = self.predict_filing_date(year, quarter)
                    days_until = (filing_date - today).days
                    
                    # Only include if within the lookahead window and not in the past
                    if 0 <= days_until <= days_ahead:
                        window = self.FILING_WINDOWS[quarter]
                        upcoming.append({
                            "report_year": year,
                            "quarter": quarter,
                            "predicted_date": filing_date,
                            "days_until": days_until,
                            "month_code": self.QUARTER_TO_MONTH[quarter],
                            "year_code": str(year)[-2:],
                            "filing_name": f"{quarter} {year}" if quarter != "10K" else f"10-K {year}",
                            "window_start": datetime(filing_date.year, window["month"], window["day_range"][0]),
                            "window_end": datetime(filing_date.year, window["month"], window["day_range"][1])
                        })
                except Exception as e:
                    logger.error(f"Error predicting filing for {quarter} {year}: {e}")
        
        # Sort by days until filing
        return sorted(upcoming, key=lambda x: x["days_until"])
    
    def get_next_filing(self) -> Dict:
        """Get the next upcoming filing."""
        upcoming = self.get_upcoming_filings(days_ahead=365)
        return upcoming[0] if upcoming else None
    
    def is_filing_window(self, quarter: str, date: datetime = None) -> bool:
        """
        Check if given date is within the filing window for a quarter.
        
        Args:
            quarter: Quarter to check
            date: Date to check (default: today)
            
        Returns:
            True if date is within filing window
        """
        if date is None:
            date = datetime.now()
        
        if quarter not in self.FILING_WINDOWS:
            return False
        
        window = self.FILING_WINDOWS[quarter]
        
        # Check if we're in the right month and day range
        if date.month != window["month"]:
            return False
        
        day_start, day_end = window["day_range"]
        return day_start <= date.day <= day_end


# Singleton instance
_filing_calendar = None

def get_filing_calendar() -> FilingCalendar:
    """Get singleton filing calendar instance."""
    global _filing_calendar
    if _filing_calendar is None:
        _filing_calendar = FilingCalendar()
    return _filing_calendar
