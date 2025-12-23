"""
Shared table parsing utilities.

Consolidates duplicate implementations from:
- src/infrastructure/extraction/formatters/excel_exporter.py
- src/infrastructure/extraction/consolidation/consolidator.py
"""

import re
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
            if re.search(r'\b20[0-3]\d\b', val_str):
                return True
            return False
        
        def column_has_data_values(data: List[List[str]], col_idx: int) -> bool:
            """
            Dynamically detect if a column contains actual data values (numbers, currency, percentages).
            
            This is data-driven - no hardcoded patterns except for universal numeric formats.
            Returns True if the column appears to contain real data, False if it's text-only.
            """
            if not data:
                return False
            
            data_indicators = 0
            total_non_empty = 0
            
            for row in data:
                if col_idx >= len(row):
                    continue
                cell = str(row[col_idx]).strip() if row[col_idx] else ''
                if not cell:
                    continue
                
                total_non_empty += 1
                
                # Check for universal data patterns (not hardcoded to specific domains)
                # Currency: starts with $ or has $ anywhere
                if '$' in cell:
                    data_indicators += 1
                    continue
                # Percentage: contains %
                if '%' in cell:
                    data_indicators += 1
                    continue
                # Parentheses for negative numbers: (123) or $(123)
                if cell.startswith('(') and cell.endswith(')'):
                    data_indicators += 1
                    continue
                # Pure numbers (with optional commas/decimals): 1,234 or 1234.56
                clean_cell = cell.replace(',', '').replace('.', '').replace('-', '').replace(' ', '')
                if clean_cell.isdigit() and len(clean_cell) > 0:
                    data_indicators += 1
                    continue
                # N/M, N/A, NM (common financial "not meaningful" indicators)
                if cell.upper() in ['N/M', 'N/A', 'NM', '-', '—', '–']:
                    data_indicators += 1
                    continue
            
            # If more than 50% of non-empty cells look like data, it's a data column
            if total_non_empty > 0 and (data_indicators / total_non_empty) > 0.5:
                return True
            return False
        
        def merge_split_columns(header: List[str], data: List[List[str]]) -> tuple:
            """
            Merge text-only columns at the start back into column 1.
            
            DYNAMIC APPROACH: Instead of hardcoding header patterns, analyze the actual
            data in each column to determine if it contains real values or just text.
            Only merge columns that appear to be accidentally split text.
            """
            if len(header) <= 2:
                return header, data  # Can't merge if only 1-2 columns
            
            # Find where data columns start by checking actual data patterns
            # Start from column 1 (column 0 is always the row label)
            data_start_col = 1  # Default: assume data starts at column 1
            
            for col_idx in range(1, len(header)):
                # Check if header looks like a date (existing logic - this is valid)
                if is_date_header(header[col_idx]):
                    data_start_col = col_idx
                    break
                
                # DYNAMIC: Check if this column actually contains data values
                if column_has_data_values(data, col_idx):
                    data_start_col = col_idx
                    break
            
            # If data starts at column 1, no merging needed
            if data_start_col <= 1:
                return header, data
            
            # Only merge if we're confident columns 1 to data_start_col-1 are text-only
            # Verify by checking if those columns have NO data values
            should_merge = True
            for col_idx in range(1, data_start_col):
                if column_has_data_values(data, col_idx):
                    # This column has data - don't merge
                    should_merge = False
                    break
            
            if not should_merge:
                return header, data
            
            # Merge columns 0 to data_start_col-1 into column 0
            new_header = [' '.join(str(h) for h in header[:data_start_col]).strip()] + list(header[data_start_col:])
            new_data = []
            for row in data:
                merged_cell = ' '.join(str(c) for c in row[:data_start_col]).strip()
                new_row = [merged_cell] + list(row[data_start_col:])
                new_data.append(new_row)
            
            return new_header, new_data
        
        def is_pure_footnote(cell: str) -> bool:
            """Check if a cell value is just a footnote reference (1-2 digit number or comma-separated)."""
            if not cell:
                return False
            cell = str(cell).strip()
            # Single or double digit number
            if cell.isdigit() and len(cell) <= 2:
                return True
            # Comma-separated footnotes like "2,3" or "1,2,3"
            if re.match(r'^\d+(?:,\d+)+$', cell):
                return True
            return False
        
        def merge_split_footnotes(header: List[str], data: List[List[str]]) -> tuple:
            """
            Merge split footnotes in data rows.
            
            When Docling incorrectly splits 'ROTCE 3' into ['ROTCE', '3', ...],
            detect the footnote in column 1 and merge it back into column 0.
            
            Handles two scenarios:
            1. Column 1 header is empty/non-data and col1 is a footnote
            2. Row has MORE columns than header (indicates split footnote leak)
            """
            if len(header) < 2:
                return header, data  # Need at least 2 columns
            
            header_col_count = len([h for h in header if str(h).strip()])  # Count non-empty headers
            
            new_data = []
            any_merged = False
            
            for row in data:
                if len(row) < 2:
                    new_data.append(row)
                    continue
                
                col0 = str(row[0]).strip() if row[0] else ''
                col1 = str(row[1]).strip() if len(row) > 1 and row[1] else ''
                
                # Scenario 1: Row has more columns than header (split footnote)
                # E.g., Header: 3 cols, Row: 4 cols -> col1 is likely a split footnote
                row_has_extra_col = len(row) > len(header) and len(header) >= 3
                
                # Scenario 2: Column 1 header is not a year/date and col1 is footnote
                col1_header = str(header[1]).strip() if len(header) > 1 else ''
                col1_header_is_data = is_date_header(header[1]) or col1_header.isdigit()
                
                should_merge = False
                
                if col0 and is_pure_footnote(col1):
                    if row_has_extra_col:
                        # Row has extra column - likely split footnote
                        should_merge = True
                    elif not col1_header_is_data:
                        # Column 1 header isn't year/data, so col1 might be footnote
                        # Check that columns after have real data
                        has_real_data = False
                        for v in row[2:]:
                            v_str = str(v).strip() if v else ''
                            if v_str and not is_pure_footnote(v_str):
                                if ('$' in v_str or '%' in v_str or 
                                    (any(c.isdigit() for c in v_str) and len(v_str) > 2)):
                                    has_real_data = True
                                    break
                        if has_real_data:
                            should_merge = True
                
                if should_merge:
                    # Merge col0 + col1 as the row label
                    merged_label = f"{col0} {col1}"
                    new_row = [merged_label] + list(row[2:])
                    new_data.append(new_row)
                    any_merged = True
                else:
                    new_data.append(list(row))
            
            # Don't change headers - just the data rows
            # The padding logic after will handle any length mismatches
            return header, new_data
        
        # Apply merge logic
        header, data = merge_split_columns(header, data)
        
        # Apply footnote merge logic (fixes "ROTCE" | "3" -> "ROTCE 3")
        header, data = merge_split_footnotes(header, data)
        
        # Pad rows to match header length
        max_cols = max(len(header), max(len(r) for r in data) if data else 0)
        header = list(header) + [''] * (max_cols - len(header))
        data = [list(r) + [''] * (max_cols - len(r)) for r in data]
        
        # Clean year floats in header (e.g., if '2025' got converted somewhere)
        # and ensure all values remain strings to prevent pandas auto-conversion
        from src.utils.excel_utils import ExcelUtils
        cleaned_header = [ExcelUtils.clean_year_string(h) if h else '' for h in header]
        
        # Create DataFrame with string dtype to prevent float conversion of years
        df = pd.DataFrame(data, columns=cleaned_header, dtype=str)
        
        # Replace 'nan' strings with empty strings
        df = df.replace('nan', '')
        
        return df
        
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
