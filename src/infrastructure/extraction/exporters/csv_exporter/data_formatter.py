"""
Data formatter for CSV tables.

Applies currency and percentage formatting to data values while preserving headers.
Uses pandas DataFrame operations for efficient processing.
"""

from dataclasses import dataclass, field
from typing import List, Optional
import pandas as pd


@dataclass
class DataFormatConfig:
    """Configuration for data formatting."""
    
    # Currency settings
    add_currency_symbol: bool = True
    add_thousand_separators: bool = True
    negative_style: str = 'parenthetical'  # 'parenthetical' or 'minus'
    
    # Percentage settings
    percentage_decimal_places: int = 1
    convert_decimal_to_percentage: bool = True  # Convert 0.18 → 18.0%
    
    # Detection settings
    use_header_detection: bool = True
    use_row_label_detection: bool = True
    use_column_header_detection: bool = True
    
    # Special values
    preserve_special_values: List[str] = field(
        default_factory=lambda: ['N/M', 'N/A', 'NM', '-%', '-']
    )


def detect_table_format(first_col_header: str) -> dict:
    """
    Detect primary format from table header.
    
    Examples:
        "$ in millions" → {'type': 'currency', 'unit': 'millions'}
        "$ in billions" → {'type': 'currency', 'unit': 'billions'}
        "$ in millions, except per share data" → {'type': 'currency', 'has_exceptions': True}
    
    Args:
        first_col_header: The first column header text
        
    Returns:
        Dict with 'type', 'unit', and 'has_exceptions' keys
    """
    header_lower = str(first_col_header).lower()
    
    result = {'type': 'number', 'unit': None, 'has_exceptions': False}
    
    if '$' in header_lower or 'dollar' in header_lower:
        result['type'] = 'currency'
        if 'billion' in header_lower:
            result['unit'] = 'billions'
        elif 'million' in header_lower:
            result['unit'] = 'millions'
        if 'except' in header_lower:
            result['has_exceptions'] = True
    
    return result


def detect_column_format(col_name: str, col_values: pd.Series) -> str:
    """
    Detect format from column name ONLY.
    
    Returns: 'percentage' or 'default'
    
    Args:
        col_name: Column name/header
        col_values: Series of column values (not used for detection, just signature compatibility)
        
    Returns:
        String indicating detected format type
    """
    col_lower = str(col_name).lower()
    
    # Check column name for % indicator
    # Only check column HEADER, not values, to avoid marking mixed columns as percentage
    if '%' in col_lower or 'change' in col_lower:
        return 'percentage'
    
    return 'default'  # Use table-level format


def detect_row_format(row_label: str) -> str:
    """
    Detect format from row label.
    
    Examples:
        'ROE' → 'percentage'
        'Expense efficiency ratio' → 'percentage'
        'Pre-tax margin' → 'percentage'
        'Margin and other lending' → 'currency' (not a margin ratio)
        'Net revenues' → 'currency' (default)
    
    Args:
        row_label: The row label (Product/Entity value)
        
    Returns:
        'percentage' or 'currency'
    """
    label_lower = str(row_label).lower().strip()
    
    # Exact matches for common ratio/percentage metrics
    exact_percentage_terms = [
        'roe', 'roa', 'rotce', 'tier 1 capital ratio', 'cet1 ratio',
        'leverage ratio', 'efficiency ratio', 'expense efficiency ratio'
    ]
    
    for term in exact_percentage_terms:
        if label_lower == term:
            return 'percentage'
    
    # Pattern-based detection for percentage metrics
    # Only match if these terms appear at END or are standalone words
    percentage_patterns = [
        'ratio',       # "Overhead ratio", "Efficiency ratio"
        'margin',      # "Pre-tax margin", "Net margin" (but NOT "Margin lending")
        'yield',       # "Bond yield"
        'rate',        # "Interest rate", "Tax rate"
        'as a percentage',
        'percent'
    ]
    
    for pattern in percentage_patterns:
        # Check if pattern is at the end of the label
        if label_lower.endswith(pattern):
            return 'percentage'
        # Check if it's a standalone word (with word boundaries)
        import re
        if re.search(rf'\b{pattern}\b', label_lower):
            # Additional check: "margin" should NOT be followed by "lending", "loan", "and", etc.
            if pattern == 'margin':
                # Skip if it's part of product names like "Margin and other", "Margin lending"
                if re.search(r'\bmargin\s+(and|lending|loan|balance)', label_lower):
                    continue
                # Only match if it's clearly a margin metric
                if re.search(r'\b(pre-tax|net|operating|profit|interest)\s+margin\b', label_lower):
                    return 'percentage'
                if label_lower.endswith('margin'): # "Net margin", "EBIT margin"
                    return 'percentage'
            elif pattern == 'rate':
                # Skip if it's part of "rate of return" (currency) vs "interest rate" (percentage)
                # Most financial "rates" are percentages
                return 'percentage'
            else:
                return 'percentage'
    
    return 'currency'  # Default for financial tables


def _format_number_as_currency(num: float, negative_style: str) -> str:
    """
    Format a numeric value as currency.
    
    Args:
        num: Numeric value to format
        negative_style: 'parenthetical' or 'minus'
        
    Returns:
        Formatted currency string
    """
    # Check if decimal (like EPS: 2.8)
    has_decimal = num != int(num) and abs(num) < 100
    
    if num < 0:
        abs_num = abs(num)
        if has_decimal:
            formatted = f"{abs_num:,.2f}"
        else:
            formatted = f"{abs_num:,.0f}"
        
        if negative_style == 'parenthetical':
            return f"(${formatted})"
        else:
            return f"-${formatted}"
    else:
        if has_decimal:
            return f"${num:,.2f}"
        else:
            return f"${num:,.0f}"


def format_currency(value: any, negative_style: str = 'parenthetical') -> str:
    """
    Format value as currency with $ and thousand separators.
    
    Args:
        value: The value to format
        negative_style: 'parenthetical' → ($1,234) or 'minus' → -$1,234
    
    Examples:
        18224         → $18,224
        -248          → ($248)
        '$ (717)'     → ($717)
        2.8           → $2.80
        '$-'          → -
        'N/M'         → N/M
    
    Returns:
        Formatted string
    """
    if pd.isna(value):
        return ''
    
    val_str = str(value).strip()
    
    # Preserve special values
    if val_str in ['N/M', 'N/A', 'NM', '-%', '-', '—']:
        return val_str if val_str != '—' else '-'
    
    # Normalize dash values
    if val_str in ['$-', '$ -', '$—', '$ —']:
        return '-'
    
    # Already formatted with $ - normalize spacing
    if '$' in val_str:
        is_negative = '(' in val_str
        clean = val_str.replace('$', '').replace(',', '').replace('(', '').replace(')', '').replace(' ', '')
        try:
            num = float(clean)
            if is_negative:
                num = -abs(num)
            return _format_number_as_currency(num, negative_style)
        except:
            return val_str
    
    # Plain numeric value
    try:
        num = float(str(value).replace(',', ''))
        return _format_number_as_currency(num, negative_style)
    except:
        return str(value)


def format_percentage(value: any, decimal_places: int = 1) -> str:
    """
    Format value as percentage with % symbol.
    
    Args:
        value: The value to format
        decimal_places: Decimal places (default 1)
    
    Examples:
        '17.4 %'      → 17.4%
        0.18          → 18.0%
        '(5)%'        → -5.0%
        '-'           → -
        '1% to 4%...' → 1% to 4%... (preserve ranges)
    
    Returns:
        Formatted string
    """
    if pd.isna(value):
        return ''
    
    val_str = str(value).strip()
    
    # Preserve special values
    if val_str in ['N/M', 'N/A', 'NM', '-%', '-', '—']:
        return val_str if val_str != '—' else '-'
    
    # Preserve percentage ranges (contains 'to' or multiple %)
    if ' to ' in val_str.lower() or val_str.count('%') > 1:
        return val_str.replace(' %', '%')  # Just normalize spacing
    
    # Already has % - normalize format
    if '%' in val_str:
        is_negative = '(' in val_str or val_str.startswith('-')
        clean = val_str.replace('%', '').replace('(', '').replace(')', '').replace(' ', '').replace('-', '')
        try:
            num = float(clean)
            if is_negative:
                num = -num
            return f"{num:.{decimal_places}f}%"
        except:
            return val_str.replace(' %', '%')
    
    # Decimal ratio (0.18 → 18.0%)
    try:
        num = float(val_str)
        if -1 <= num <= 1 and num != 0:
            num = num * 100
        return f"{num:.{decimal_places}f}%"
    except:
        return str(value)


class DataFormatter:
    """
    Formats data values in CSV tables using pandas.
    
    Applies:
    - Currency formatting: $ with thousand separators
    - Percentage formatting: % symbol
    - Negative normalization: parenthetical or minus
    """
    
    def __init__(self, config: DataFormatConfig = None):
        """
        Initialize formatter with optional config.
        
        Args:
            config: DataFormatConfig instance (uses defaults if None)
        """
        self.config = config or DataFormatConfig()
    
    def format_table(self, df: pd.DataFrame, table_header: str = None) -> pd.DataFrame:
        """
        Format all data columns in the table using CELL-BASED detection.
        
        Simple rule:
        - If cell value contains '%' → format as percentage
        - Otherwise → format as currency ($)
        
        IMPORTANT: Only DATA VALUES are formatted, NOT headers.
        - Column headers (Q3-QTD-2025, % change) remain unchanged
        - Row labels (Product/Entity column) remain unchanged  
        - Only numeric/formatted values in data cells are processed
        
        Args:
            df: DataFrame with Category, Product/Entity, and data columns
            table_header: First column header (e.g., "$ in millions") - not used in cell-based approach
        
        Returns:
            DataFrame with formatted data values (headers unchanged)
        """
        result = df.copy()
        
        # Get data columns (skip Category and Product/Entity - these are labels, not data)
        # Headers themselves are NOT formatted, only the values under them
        data_columns = [c for c in df.columns if c not in ['Category', 'Product/Entity']]
        
        for col in data_columns:
            # Convert to object dtype to preserve string formatting
            result[col] = result[col].astype(object)
            
            # Apply formatting cell by cell based on cell value
            for idx in df.index:
                value = df.at[idx, col]
                
                # Skip NaN/empty values
                if pd.isna(value):
                    result.at[idx, col] = ''
                    continue
                
                # Check if cell contains % symbol → percentage format
                # Otherwise → currency format
                val_str = str(value).strip()
                
                if '%' in val_str:
                    # Cell contains %, format as percentage
                    result.at[idx, col] = format_percentage(
                        value, 
                        self.config.percentage_decimal_places
                    )
                else:
                    # No %, format as currency
                    result.at[idx, col] = format_currency(
                        value,
                        self.config.negative_style
                    )
        
        return result
