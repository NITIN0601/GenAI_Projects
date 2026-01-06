"""
Table finder utilities for the Process step.

Functions for detecting table boundaries within Excel worksheets.
"""

from typing import List, Dict, Optional
from src.utils import get_logger

logger = get_logger(__name__)


def find_all_tables(ws) -> List[Dict]:
    """
    Find all tables in a worksheet by identifying table boundaries.
    
    Tables are marked by:
    - "Table Title:" rows
    - "Source:" or "Source(s):" rows
    - Empty rows between tables
    
    Args:
        ws: openpyxl Worksheet object
        
    Returns:
        List of dicts with 'start_row', 'end_row', 'header_row', 'source_row'
    """
    tables = []
    current_table_start = None
    
    for row in range(1, ws.max_row + 1):
        col_a = ws.cell(row, 1).value
        
        if col_a:
            col_a_str = str(col_a).strip()
            col_a_lower = col_a_str.lower()
            
            # Found a new table marker - must START with "Source" (not contain it elsewhere)
            is_source_row = (
                col_a_lower.startswith('source(s):') or
                col_a_lower.startswith('source:')
            )
            
            if is_source_row:
                # If we had a previous table, close it
                if current_table_start is not None:
                    tables.append({
                        'start_row': current_table_start,
                        'end_row': row - 1,
                        'source_row': current_table_start  # Use the table's OWN source row
                    })
                current_table_start = row
    
    # Don't forget the last table
    if current_table_start is not None:
        tables.append({
            'start_row': current_table_start, 
            'end_row': ws.max_row,
            'source_row': current_table_start
        })
    
    # For each table, find the actual data header row (first row after source with content in col B)
    for table in tables:
        source_row = table['source_row']
        header_row = None
        
        for row in range(source_row + 1, min(table['end_row'] + 1, source_row + 10)):
            col_b = ws.cell(row, 2).value
            if col_b and str(col_b).strip():
                header_row = row
                break
        
        table['header_row'] = header_row if header_row else source_row + 2
    
    return tables


def find_first_data_row_after_source(ws) -> int:
    """
    Find the first row with data after the Source(s): marker.
    
    Scans for patterns like "Table Title:", "Source:", "Source(s):" and returns
    the first row after that which contains data.
    
    Args:
        ws: openpyxl Worksheet object
    
    Returns:
        Row number where data starts (default: 13 if pattern not found)
    """
    source_row = None
    
    # Scan for Source(s): or Source: marker
    for row in range(1, min(ws.max_row + 1, 30)):
        cell_val = ws.cell(row, 1).value
        if cell_val:
            cell_str = str(cell_val).strip().lower()
            if cell_str.startswith('source(s):') or cell_str.startswith('source:'):
                source_row = row
                break
    
    if source_row is None:
        # No Source: found, return default
        return 13
    
    # Find first row with data after source row
    for row in range(source_row + 1, min(ws.max_row + 1, source_row + 10)):
        # Check if row has any content
        for col in range(1, min(ws.max_column + 1, 10)):
            cell_val = ws.cell(row, col).value
            if cell_val and str(cell_val).strip():
                return row
    
    return source_row + 1  # Default to row after source


def find_data_start_row(ws) -> Optional[int]:
    """
    Find the first row that contains actual data (has numeric values in data columns).
    
    Skips:
    - Empty rows
    - Header rows (period types, years)
    - Section label rows (text only in column A)
    
    Args:
        ws: openpyxl Worksheet object
        
    Returns:
        Row number where data starts, or None if not found
    """
    # Dynamically find where headers/data start after Source: marker
    header_start = find_first_data_row_after_source(ws)
    
    for row in range(header_start, min(ws.max_row + 1, header_start + 20)):
        # Count numeric values in data columns (columns 2+)
        numeric_count = 0
        for col in range(2, min(ws.max_column + 1, 10)):
            val = ws.cell(row, col).value
            if val is not None and str(val).strip():
                val_str = str(val).strip()
                # Skip if it looks like a header pattern
                if any(kw in val_str.lower() for kw in ['months ended', 'at ', 'as of', 'year ended']):
                    continue
                # Skip if it's just a year
                if len(val_str) == 4 and val_str.isdigit():
                    continue
                # Try to parse as number
                try:
                    clean_val = val_str.replace('%', '').replace(',', '').replace('$', '').replace('-', '').strip()
                    if clean_val:
                        float(clean_val)
                        numeric_count += 1
                except (ValueError, TypeError):
                    pass
        
        # Need at least 1 numeric value to consider it a data row
        if numeric_count >= 1:
            return row
    
    return None
