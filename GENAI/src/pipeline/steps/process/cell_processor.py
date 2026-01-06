"""
Cell processor utilities for the Process step.

Functions for processing individual cell values and applying Excel formatting.
"""

import re
from typing import Tuple, Any, Optional

from src.utils.excel_utils import ExcelUtils
from src.utils.text_normalizer import normalize_text
from src.pipeline.steps.process.constants import (
    CURRENCY_FORMAT,
    PERCENT_FORMAT,
    NEGATIVE_CURRENCY_FORMAT,
)


def is_numeric_value(value_str: str) -> bool:
    """
    Check if a string value represents a number (data, not header).
    
    Args:
        value_str: String value to check
        
    Returns:
        True if the value appears to be numeric data
    """
    if not value_str:
        return False
    
    # Clean the value
    clean = value_str.strip()
    
    # Skip common header patterns
    if any(kw in clean.lower() for kw in ['in millions', 'in billions', '$', 'months ended', 'at ']):
        return False
    
    # 4-digit years (2020-2099) are HEADERS, not numeric data
    if re.match(r'^20\d{2}$', clean):
        return False
    
    # Try to parse as number
    try:
        clean_num = clean.replace('%', '').replace(',', '').replace('$', '').replace('-', '').strip()
        if clean_num:
            float(clean_num)
            return True
    except (ValueError, TypeError):
        pass
    
    return False


def process_cell_value(value: Any, row_idx: int, col_idx: int) -> Tuple[Any, Optional[str]]:
    """
    Process a single cell value and determine Excel format.
    
    Handles:
    - OCR broken words fix (for column A)
    - Footnote reference cleanup
    - Currency conversion with formatting
    - Percentage conversion with formatting
    
    Args:
        value: Cell value (can be string, int, float, or None)
        row_idx: Row index (1-indexed)
        col_idx: Column index (1-indexed)
        
    Returns:
        Tuple of (processed_value, excel_format_or_None)
    """
    if value is None:
        return value, None
    
    str_value = str(value).strip()
    
    # Skip empty values
    if not str_value:
        return value, None
    
    # Skip special text values
    if str_value.lower() in ['n/a', '-', '—', 'nm', 'n.a.', '']:
        return value, None
    
    # Already a number? Check if it needs formatting
    if isinstance(value, (int, float)):
        # Determine format based on magnitude (crude heuristic)
        if abs(value) < 1 and value != 0:
            # Likely a percentage (0.155 = 15.5%)
            return value, PERCENT_FORMAT
        else:
            return value, CURRENCY_FORMAT
    
    # Fix OCR broken words and normalize text (for row labels in column A only)
    if isinstance(value, str) and col_idx == 1:
        str_value = ExcelUtils.fix_ocr_broken_words(str_value)
        str_value = ExcelUtils.clean_footnote_references(str_value)
        # Apply text normalization (spaces around dashes, etc.)
        str_value = normalize_text(str_value)
        return str_value, None
    
    # Try percentage conversion first (contains %)
    if isinstance(value, str) and '%' in str_value:
        try:
            pct_str = str_value.replace('%', '').replace(',', '').strip()
            pct_val = float(pct_str)
            return pct_val / 100.0, PERCENT_FORMAT  # 15.5% -> 0.155
        except (ValueError, TypeError):
            pass
    
    # Try currency/negative conversion
    if isinstance(value, str):
        cleaned = ExcelUtils.clean_currency_value(str_value)
        if isinstance(cleaned, (int, float)) and cleaned != value:
            return cleaned, NEGATIVE_CURRENCY_FORMAT if cleaned < 0 else CURRENCY_FORMAT
    
    return str_value if isinstance(value, str) else value, None
