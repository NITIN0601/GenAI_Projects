"""
Key-value table handler for the Process step.

Functions for detecting and processing key-value style tables that should
skip standard header normalization.
"""

from typing import Dict, Callable, Any

from src.pipeline.steps.process.constants import KEY_VALUE_LABELS
from src.pipeline.steps.process.table_finder import find_first_data_row_after_source


def is_key_value_table(ws) -> bool:
    """
    Detect if a worksheet contains a key-value table (not a data table with column headers).
    
    Key-value tables have:
    - Row labels in column A (e.g., "Announcement date", "Amount per share")
    - Single data values in column B (not spanning headers)
    - Very few columns with data (typically 2-3)
    - Row labels that look like field names, not data categories
    
    Args:
        ws: openpyxl Worksheet object
        
    Returns:
        True if this appears to be a key-value table
    """
    # Dynamically find where data starts
    data_start = find_first_data_row_after_source(ws)
    
    # Check data rows for key-value patterns
    kv_pattern_count = 0
    total_rows_checked = 0
    
    for row in range(data_start, min(ws.max_row + 1, data_start + 7)):
        col_a = ws.cell(row, 1).value
        col_b = ws.cell(row, 2).value
        col_c = ws.cell(row, 3).value
        
        if not col_a:
            continue
        
        total_rows_checked += 1
        col_a_lower = str(col_a).lower().strip()
        
        # Check if column A looks like a key-value label
        is_kv_label = any(label in col_a_lower for label in KEY_VALUE_LABELS)
        
        # Only count explicit key-value label matches, not generic single-column checks
        if is_kv_label:
            kv_pattern_count += 1
    
    # Require at least 2 explicit key-value labels to treat as key-value table
    return total_rows_checked > 0 and kv_pattern_count >= 2


def process_data_cells_only(
    ws, 
    stats: Dict[str, Any], 
    process_cell_func: Callable
) -> None:
    """
    Process data cells for numeric formatting only, without header normalization.
    Used for key-value tables that should not have headers modified.
    
    Args:
        ws: openpyxl Worksheet object
        stats: Stats dictionary to update
        process_cell_func: Function to process individual cell values
    """
    # Dynamically find where data starts
    data_start = find_first_data_row_after_source(ws)
    
    # Just process percentage and numeric formatting
    for row in range(data_start, ws.max_row + 1):
        for col in range(1, ws.max_column + 1):
            cell = ws.cell(row, col)
            if cell.value is None:
                continue
            
            value = cell.value
            new_value, number_format = process_cell_func(value, row, col)
            
            if new_value != value:
                cell.value = new_value
                stats['cells_formatted'] = stats.get('cells_formatted', 0) + 1
            
            if number_format:
                cell.number_format = number_format
