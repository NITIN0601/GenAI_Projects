"""
Shared table parsing utilities.

Consolidates duplicate implementations from:
- src/infrastructure/extraction/formatters/excel_exporter.py
- src/infrastructure/extraction/consolidation/consolidator.py
"""

import pandas as pd
from typing import List, Optional

from src.utils import get_logger

logger = get_logger(__name__)


def parse_markdown_table(
    content: str,
    handle_colon_separator: bool = False
) -> pd.DataFrame:
    """
    Parse markdown/text table to DataFrame with currency cleaning.
    
    Args:
        content: Markdown table content with | delimiters
        handle_colon_separator: If True, also parse "key: value" lines
        
    Returns:
        DataFrame with table data, empty DataFrame on error
        
    Example:
        >>> content = '''
        ... | Metric | 2024 | 2023 |
        ... |--------|------|------|
        ... | Revenue | $100 | $90 |
        ... '''
        >>> df = parse_markdown_table(content)
        >>> print(df.columns.tolist())
        ['Metric', '2024', '2023']
    """
    try:
        from src.utils.extraction_utils import CurrencyValueCleaner
        
        # Clean currency values first
        cleaned_content = CurrencyValueCleaner.clean_table_rows(content)
        
        lines = [l.strip() for l in cleaned_content.split('\n') if l.strip()]
        
        # Remove separator lines (e.g., |---|---|)
        lines = [l for l in lines if not all(c in '|-: ' for c in l)]
        
        if not lines:
            return pd.DataFrame()
        
        rows = []
        for line in lines:
            if '|' in line:
                # Parse pipe-delimited table
                cells = [c.strip() for c in line.split('|')]
                cells = [c for c in cells if c]  # Remove empty strings
                cells = CurrencyValueCleaner.clean_currency_cells(cells)
                if cells:
                    rows.append(cells)
            elif handle_colon_separator and ':' in line:
                # Parse "key: value" format (for consolidator)
                parts = line.split(':', 1)
                if len(parts) == 2:
                    rows.append([parts[0].strip(), parts[1].strip()])
        
        if not rows or len(rows) < 2:
            return pd.DataFrame()
        
        # First row is header
        header = rows[0]
        data = rows[1:]
        
        # Pad rows to match header length
        max_cols = max(len(header), max(len(r) for r in data) if data else 0)
        header = header + [''] * (max_cols - len(header))
        data = [r + [''] * (max_cols - len(r)) for r in data]
        
        return pd.DataFrame(data, columns=header)
        
    except Exception as e:
        logger.error(f"Error parsing table content: {e}")
        return pd.DataFrame()


def quarter_to_month(quarter: str) -> int:
    """
    Convert quarter string to end-of-quarter month number.
    
    Args:
        quarter: Quarter string (Q1, Q2, Q3, Q4)
        
    Returns:
        Month number (3, 6, 9, 12) or 12 if not recognized
    """
    if not quarter:
        return 12
    
    quarter = quarter.upper()
    if 'Q1' in quarter:
        return 3
    elif 'Q2' in quarter:
        return 6
    elif 'Q3' in quarter:
        return 9
    elif 'Q4' in quarter or '10K' in quarter:
        return 12
    return 12


def quarter_to_number(quarter: Optional[str]) -> int:
    """
    Convert quarter string to quarter number (1-4).
    
    Args:
        quarter: Quarter string (Q1, Q2, Q3, Q4)
        
    Returns:
        Quarter number (1-4) or 5 if not recognized (for sorting)
    """
    if not quarter:
        return 5
    
    quarter = quarter.upper()
    if 'Q1' in quarter:
        return 1
    elif 'Q2' in quarter:
        return 2
    elif 'Q3' in quarter:
        return 3
    elif 'Q4' in quarter or '10K' in quarter:
        return 4
    return 5


def get_period_end_date(year: Optional[int], quarter: Optional[str]) -> str:
    """
    Get period end date string (YYYY-MM-DD) for a year/quarter.
    
    Args:
        year: Fiscal year
        quarter: Quarter string (Q1, Q2, Q3, Q4)
        
    Returns:
        Date string in YYYY-MM-DD format
    """
    if not year:
        return "Unknown"
    
    if not quarter:
        return f"{year}-12-31"
    
    quarter = quarter.upper()
    
    if "Q1" in quarter:
        return f"{year}-03-31"
    elif "Q2" in quarter:
        return f"{year}-06-30"
    elif "Q3" in quarter:
        return f"{year}-09-30"
    elif "Q4" in quarter or "10-K" in quarter or "10K" in quarter:
        return f"{year}-12-31"
    else:
        return f"{year}-12-31"
