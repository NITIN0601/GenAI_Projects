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
    handle_colon_separator: bool = False,
    title: Optional[str] = None
) -> pd.DataFrame:
    """
    Parse markdown/text table to DataFrame with currency cleaning.
    
    Args:
        content: Markdown table content with | delimiters
        handle_colon_separator: If True, also parse "key: value" lines
        title: Optional table title for cleanup (removes title from data/headers)
        
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
        
        # Helper to check if a row looks like the title
        def is_title_row(row_line: str, title: str) -> bool:
            if not title:
                return False
            # Strip pipes
            content = row_line.strip('|').strip()
            # Simple fuzzy match or exact match
            from difflib import SequenceMatcher
            ratio = SequenceMatcher(None, content.lower(), title.lower()).ratio()
            return ratio > 0.8 or title.lower() in content.lower()
        
        # Remove separator lines (e.g., |---|---|)
        # But carefully, so we can detect separator index if needed for header/data split
        # Actually parse_markdown_table logic here is simpler than TableStructureFormatter
        # It assumes first parsed row is header.
        
        parsed_rows = []
        separator_seen = False
        
        for line in lines:
            if all(c in '|-: ' for c in line) and '|' in line:
                separator_seen = True
                continue
                
            if '|' in line:
                # Parse pipe-delimited table
                cells = [c.strip() for c in line.split('|')]
                # Remove leading/trailing empty parts from pipe split, but PRESERVE structure
                # e.g., "| | A | B |" → ['', '', 'A', 'B', ''] → ['', 'A', 'B']
                if cells and not cells[0]:
                    cells = cells[1:]  # Remove leading empty string
                if cells and not cells[-1]:
                    cells = cells[:-1]  # Remove trailing empty string
                cells = CurrencyValueCleaner.clean_currency_cells(cells)
                if cells:
                    parsed_rows.append(cells)
            elif handle_colon_separator and ':' in line:
                # Parse "key: value" format (for consolidator)
                parts = line.split(':', 1)
                if len(parts) == 2:
                    parsed_rows.append([parts[0].strip(), parts[1].strip()])
        
        if not parsed_rows:
            return pd.DataFrame()
            
        # Post-processing for title row content
        if title and len(parsed_rows) > 0:
            first_row_str = " ".join(parsed_rows[0])
            if is_title_row(first_row_str, title):
                 # If first row is title, drop it
                 parsed_rows.pop(0)
        
        if not parsed_rows or len(parsed_rows) < 2:
            return pd.DataFrame()
        
        # First row is header
        header = parsed_rows[0]
        data = parsed_rows[1:]
        
        # === FIX SPLIT COLUMNS ===
        # Detect if Docling split text across multiple columns
        # Merge text-only columns back into column 1 (row labels)
        def is_date_header(header_val: str) -> bool:
            """Check if a header looks like a date column header (e.g., 'At March 31, 2025')."""
            val_str = str(header_val).strip().lower()
            if not val_str:
                return False
            # Check for date patterns in header
            if ('at ' in val_str or 
                'as of' in val_str or
                any(month in val_str for month in 
                    ['january', 'february', 'march', 'april', 'may', 'june', 
                     'july', 'august', 'september', 'october', 'november', 'december',
                     'jan', 'feb', 'mar', 'apr', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec'])):
                return True
            # Check for year patterns (2020-2030)
            import re
            if re.search(r'\b20[0-3]\d\b', val_str):
                return True
            return False
        
        def merge_split_columns(header: List[str], data: List[List[str]]) -> tuple:
            """Merge text-only columns at the start back into column 1."""
            if len(header) <= 2:
                return header, data  # Can't merge if only 1-2 columns
            
            # Find where date/data columns start (first column with date header)
            data_start_col = len(header)  # Default: no data columns found
            for col_idx in range(1, len(header)):
                if is_date_header(header[col_idx]):
                    data_start_col = col_idx
                    break
            
            # If no date column found, check last column - it might be the data
            if data_start_col >= len(header):
                # Fallback: keep only last 2 columns as data if header has 4+ columns
                if len(header) >= 4:
                    data_start_col = len(header) - 2
                else:
                    return header, data  # Can't determine, don't merge
            
            # If data starts at column 1, no merging needed
            if data_start_col <= 1:
                return header, data
            
            # Merge columns 0 to data_start_col-1 into column 0
            new_header = [' '.join(str(h) for h in header[:data_start_col]).strip()] + list(header[data_start_col:])
            new_data = []
            for row in data:
                merged_cell = ' '.join(str(c) for c in row[:data_start_col]).strip()
                new_row = [merged_cell] + list(row[data_start_col:])
                new_data.append(new_row)
            
            return new_header, new_data
        
        # Apply merge logic
        header, data = merge_split_columns(header, data)
        
        # Pad rows to match header length
        max_cols = max(len(header), max(len(r) for r in data) if data else 0)
        header = list(header) + [''] * (max_cols - len(header))
        data = [list(r) + [''] * (max_cols - len(r)) for r in data]
        
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
