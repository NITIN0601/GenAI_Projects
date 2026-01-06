"""
Key-Value Table Detector - Detect non-data tables.

Extracted from process.py for modularity.

Key-value tables have:
- Row labels in column A
- Single data values in column B
- Very few columns with data
"""

from typing import List
from src.utils import get_logger

logger = get_logger(__name__)


class KeyValueTableDetector:
    """
    Detect key-value tables that should not have headers modified.
    
    Examples of key-value tables:
    - Dividend announcement tables
    - Company info tables
    - Single-value summary tables
    """
    
    # Common key-value table labels
    KEY_VALUE_LABELS = [
        'announcement date', 'record date', 'payment date',
        'amount per share', 'total amount', 'quarter ended',
        'fiscal year', 'company name', 'ticker symbol',
        'exchange', 'industry', 'sector'
    ]
    
    @classmethod
    def is_key_value_table(cls, ws, check_rows: int = 7) -> bool:
        """
        Detect if worksheet contains a key-value table.
        
        Args:
            ws: openpyxl worksheet
            check_rows: Number of rows to check
            
        Returns:
            True if likely a key-value table
        """
        key_value_indicators = 0
        
        for row in range(1, min(ws.max_row + 1, check_rows + 1)):
            col_a = ws.cell(row, 1).value
            col_b = ws.cell(row, 2).value
            col_c = ws.cell(row, 3).value
            
            if col_a and col_b:
                label = str(col_a).strip().lower()
                
                # Check for key-value patterns
                if any(kw in label for kw in cls.KEY_VALUE_LABELS):
                    key_value_indicators += 1
                
                # Key-value tables have data in B but not in C
                if col_b and not col_c:
                    key_value_indicators += 0.5
        
        # If more than 2 indicators, likely key-value table
        return key_value_indicators >= 2
    
    @classmethod
    def get_key_value_pairs(cls, ws, max_rows: int = 20) -> List[tuple]:
        """
        Extract key-value pairs from a key-value table.
        
        Returns:
            List of (key, value) tuples
        """
        pairs = []
        
        for row in range(1, min(ws.max_row + 1, max_rows + 1)):
            key = ws.cell(row, 1).value
            value = ws.cell(row, 2).value
            
            if key and value:
                pairs.append((str(key).strip(), value))
        
        return pairs


__all__ = ['KeyValueTableDetector']
