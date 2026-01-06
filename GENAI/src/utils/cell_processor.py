"""
Cell Processor - Reusable cell value processing utilities.

Extracted from process.py for modularity and reusability.

Used by: ProcessStep, other processing modules
"""

import re
from typing import Tuple, Optional, Any

from src.utils.excel_utils import ExcelUtils
from src.utils.text_normalizer import normalize_text


# Excel number formats
CURRENCY_FORMAT = '$#,##0.00'
NEGATIVE_CURRENCY_FORMAT = '$#,##0.00_);[Red]($#,##0.00)'
PERCENT_FORMAT = '0.00%'


class CellProcessor:
    """
    Reusable cell value processor for Excel data.
    
    Provides:
    - Numeric value detection (distinguishes data from headers)
    - Currency parsing and formatting
    - Percentage conversion
    - OCR text cleanup
    - Footnote reference removal
    
    Design: Stateless class methods for horizontal scaling.
    """
    
    @classmethod
    def is_numeric_value(cls, value_str: str) -> bool:
        """
        Check if a string represents numeric data (not a header).
        
        Args:
            value_str: String value to check
            
        Returns:
            True if value is numeric data
        """
        if not value_str:
            return False
        
        clean = value_str.strip()
        
        # Skip header patterns
        if any(kw in clean.lower() for kw in ['in millions', 'in billions', '$', 'months ended', 'at ']):
            return False
        
        # Years (2020-2099) are headers, not data
        if re.match(r'^20\d{2}$', clean):
            return False
        
        try:
            clean_num = clean.replace('%', '').replace(',', '').replace('$', '').replace('-', '').strip()
            if clean_num:
                float(clean_num)
                return True
        except (ValueError, TypeError):
            pass
        
        return False
    
    @classmethod
    def process_cell_value(
        cls, 
        value: Any, 
        row_idx: int, 
        col_idx: int
    ) -> Tuple[Any, Optional[str]]:
        """
        Process a cell value and determine Excel format.
        
        Args:
            value: Cell value to process
            row_idx: Row index (1-based)
            col_idx: Column index (1-based, 1=row labels)
            
        Returns:
            Tuple of (processed_value, excel_format_or_None)
        """
        if value is None:
            return value, None
        
        str_value = str(value).strip()
        
        if not str_value:
            return value, None
        
        # Special text values
        if str_value.lower() in ['n/a', '-', '—', 'nm', 'n.a.', '']:
            return value, None
        
        # Already numeric
        if isinstance(value, (int, float)):
            if abs(value) < 1 and value != 0:
                return value, PERCENT_FORMAT
            return value, CURRENCY_FORMAT
        
        # Row labels (column A) - fix OCR issues
        if isinstance(value, str) and col_idx == 1:
            str_value = ExcelUtils.fix_ocr_broken_words(str_value)
            str_value = ExcelUtils.clean_footnote_references(str_value)
            str_value = normalize_text(str_value)
            return str_value, None
        
        # Percentage conversion
        if isinstance(value, str) and '%' in str_value:
            try:
                pct_str = str_value.replace('%', '').replace(',', '').strip()
                pct_val = float(pct_str)
                return pct_val / 100.0, PERCENT_FORMAT
            except (ValueError, TypeError):
                pass
        
        # Currency conversion
        if isinstance(value, str):
            cleaned = ExcelUtils.clean_currency_value(str_value)
            if isinstance(cleaned, (int, float)) and cleaned != value:
                return cleaned, NEGATIVE_CURRENCY_FORMAT if cleaned < 0 else CURRENCY_FORMAT
        
        return str_value if isinstance(value, str) else value, None


# Module-level exports for convenience
__all__ = [
    'CellProcessor',
    'CURRENCY_FORMAT',
    'NEGATIVE_CURRENCY_FORMAT', 
    'PERCENT_FORMAT',
]
