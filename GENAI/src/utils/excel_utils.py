"""
Shared Excel Utilities.

Common utility functions used by both ExcelTableExporter and ConsolidatedExcelExporter.
"""

import re
from typing import Optional


class ExcelUtils:
    """Shared utility functions for Excel export operations."""
    
    @staticmethod
    def get_column_letter(idx: int) -> str:
        """
        Convert column index to Excel column letter.
        
        Args:
            idx: 0-based column index (0=A, 25=Z, 26=AA, etc.)
            
        Returns:
            Excel column letter(s)
        """
        result = ""
        while idx >= 0:
            result = chr(idx % 26 + 65) + result
            idx = idx // 26 - 1
        return result
    
    @staticmethod
    def sanitize_sheet_name(name: str, max_length: int = 31) -> str:
        """
        Sanitize string for Excel sheet name.
        
        Excel sheet name rules:
        - Max 31 characters
        - No: [ ] : * ? / \\
        
        Args:
            name: Sheet name to sanitize
            max_length: Maximum length (default 31)
            
        Returns:
            Sanitized sheet name
        """
        if not name:
            return "Sheet"
        
        # Remove invalid characters
        sanitized = re.sub(r'[\[\]:*?/\\]', '', name)
        
        # Truncate if needed
        if len(sanitized) > max_length:
            sanitized = sanitized[:max_length-3] + "..."
        
        return sanitized.strip() or "Sheet"
    
    @staticmethod
    def normalize_title_for_grouping(title: str, clean_row_ranges: bool = True) -> str:
        """
        Normalize title for case-insensitive grouping.
        
        Ensures tables like:
        - "Difference Between Contractual..."
        - "Difference between Contractual..."
        are grouped together.
        
        Args:
            title: Title to normalize
            clean_row_ranges: If True, remove (Rows X-Y) patterns
            
        Returns:
            Normalized lowercase title
        """
        if not title:
            return ""
        
        result = title.lower().strip()
        
        if clean_row_ranges:
            # Remove row range patterns like (Rows 1-10)
            result = re.sub(r'\s*\(rows?\s*\d+[-–]\d+\)\s*$', '', result, flags=re.IGNORECASE)
        
        # Remove leading section numbers
        result = re.sub(r'^\d+[\.:\s]+\s*', '', result)
        
        # Remove Note/Table prefixes
        result = re.sub(r'^note\s+\d+\.?\s*[-–:]?\s*', '', result, flags=re.IGNORECASE)
        result = re.sub(r'^table\s+\d+\.?\s*[-–:]?\s*', '', result, flags=re.IGNORECASE)
        
        # Normalize whitespace
        result = re.sub(r'\s+', ' ', result)
        
        return result.strip() or "untitled"
    
    @staticmethod
    def normalize_row_label(label: str) -> str:
        """
        Normalize row label for matching during consolidation.
        
        Removes footnote markers, superscripts, and extra whitespace.
        
        Handles patterns like:
        - 'Cash and Cash Equivalents 1 :' -> 'cash and cash equivalents'
        - 'Securities purchased under agreements to resell 3:' -> 'securities purchased...'
        - 'Customer receivables and Other 1,10 :' -> 'customer receivables and other'
        - 'Total assets (1)(2)' -> 'total assets'
        - 'Net income¹²' -> 'net income'
        
        Args:
            label: Row label to normalize
            
        Returns:
            Normalized lowercase label
        """
        if not label:
            return ""
        
        import pandas as pd
        if pd.isna(label):
            return ""
        
        label = str(label).strip()
        
        # Remove unicode superscript characters
        superscript_map = {
            '¹': '', '²': '', '³': '', '⁴': '', '⁵': '',
            '⁶': '', '⁷': '', '⁸': '', '⁹': '', '⁰': ''
        }
        for sup, replacement in superscript_map.items():
            label = label.replace(sup, replacement)
        
        # Remove footnote patterns
        # Pattern: Trailing numbers before optional colon: "Text 1 :" or "Text 1,10 :"
        label = re.sub(r'\s+[\d,]+\s*:?\s*$', '', label)
        # Pattern: Just trailing numbers: "Text 2" or "Text 1 2 3"
        label = re.sub(r'\s+\d+(?:\s+\d+)*\s*$', '', label)
        # Pattern: Parenthesized: "(1)" or "(1)(2)"
        label = re.sub(r'\s*\(\d+\)\s*', ' ', label)
        # Pattern: Bracketed: "[1]" or "[2]"
        label = re.sub(r'\s*\[\d+\]\s*', ' ', label)
        # Pattern: Braced: "{1}" or "{2}"
        label = re.sub(r'\s*\{\d+\}\s*', ' ', label)
        # Pattern: Asterisks
        label = re.sub(r'\*+', ' ', label)
        # Pattern: Trailing colon or period
        label = re.sub(r'[:\.]+\s*$', '', label)
        # Normalize whitespace
        label = re.sub(r'\s+', ' ', label)
        
        return label.lower().strip()
    
    @staticmethod
    def clean_footnote_references(text: str) -> str:
        """
        Clean footnote references from text for display purposes.
        
        Unlike normalize_row_label (which returns lowercase for matching),
        this preserves the original case for display.
        
        Args:
            text: Text with potential footnote references
            
        Returns:
            Cleaned text with original case preserved
        """
        if not text:
            return ""
        
        import pandas as pd
        if pd.isna(text):
            return ""
        
        text = str(text).strip()
        
        # Remove unicode superscript characters
        superscript_map = {
            '¹': '', '²': '', '³': '', '⁴': '', '⁵': '',
            '⁶': '', '⁷': '', '⁸': '', '⁹': '', '⁰': ''
        }
        for sup, replacement in superscript_map.items():
            text = text.replace(sup, replacement)
        
        # Remove footnote patterns (preserving case)
        # Pattern: Trailing numbers before optional colon: "Text 1 :" or "Text 1,10 :"
        text = re.sub(r'\s+[\d,]+\s*:?\s*$', '', text)
        # Pattern: Just trailing numbers: "Text 2"
        text = re.sub(r'\s+\d+(?:\s+\d+)*\s*$', '', text)
        # Pattern: Parenthesized: "(1)"
        text = re.sub(r'\s*\(\d+\)\s*', ' ', text)
        # Pattern: Bracketed: "[1]"
        text = re.sub(r'\s*\[\d+\]\s*', ' ', text)
        # Pattern: Braced: "{1}"
        text = re.sub(r'\s*\{\d+\}\s*', ' ', text)
        # Pattern: Asterisks
        text = re.sub(r'\*+', ' ', text)
        # Normalize multiple spaces to single
        text = re.sub(r'\s+', ' ', text)
        
        return text.strip()
    
    @staticmethod
    def clean_currency_value(val) -> any:
        """
        Convert currency string to float, keep special values as string.
        
        Centralizes currency parsing logic used by both exporters.
        
        Args:
            val: Cell value (could be string, float, or NaN)
            
        Returns:
            Float for numeric values, string for special values (N/A, -, etc.)
            
        Examples:
            '$1,234' -> 1234.0
            '($500)' -> -500.0
            'N/A' -> 'N/A'
            '-' -> '-'
        """
        import pandas as pd
        
        if pd.isna(val):
            return val
        
        val_str = str(val).strip()
        
        # Keep special values as strings
        special_values = ['N/A', 'N/M', '-', '—', '', 'nan', 'NaN']
        if val_str in special_values:
            return val_str if val_str not in ['nan', 'NaN'] else ''
        
        # Check if it looks like a currency value
        if '$' in val_str or ',' in val_str:
            # Strip $ and commas, try to convert to float
            cleaned = val_str.replace('$', '').replace(',', '').strip()
            # Handle parentheses for negative numbers: ($123) -> -123
            if cleaned.startswith('(') and cleaned.endswith(')'):
                cleaned = '-' + cleaned[1:-1]
            try:
                return float(cleaned)
            except ValueError:
                return val_str
        
        # Try to convert pure numeric strings to float
        try:
            return float(val_str)
        except ValueError:
            return val_str
    
    @staticmethod
    def clean_year_string(val) -> str:
        """
        Remove .0 suffix from year values (e.g., 2025.0 -> '2025').
        
        Centralizes the year cleaning regex that was duplicated across files.
        
        Args:
            val: Value that might be a year (int, float, or string)
            
        Returns:
            Cleaned string representation
            
        Examples:
            2025.0 -> '2025'
            '2024.0' -> '2024'
            'March 31, 2025.0' -> 'March 31, 2025'
        """
        if val is None:
            return ''
        
        # Handle float years directly
        if isinstance(val, float) and val == int(val) and 2000 <= val <= 2099:
            return str(int(val))
        
        # Handle string with .0 suffix
        val_str = str(val)
        # Remove .0 from year values in strings
        val_str = re.sub(r'\b(20\d{2})\.0\b', r'\1', val_str)
        
        return val_str
    
    @staticmethod
    def ensure_string_header(val) -> str:
        """
        Ensure header value is a clean string without .0 suffix.
        
        Combines null handling with year cleaning for header cells.
        
        Args:
            val: Header value (could be int, float, string, or None)
            
        Returns:
            Clean string suitable for Excel header
        """
        import pandas as pd
        
        if pd.isna(val):
            return ''
        if isinstance(val, float) and val == int(val):
            return str(int(val))
        return ExcelUtils.clean_year_string(val)
    
    @staticmethod
    def detect_report_type(source: str) -> str:
        """
        Detect report type from source filename.
        
        Args:
            source: Source filename
            
        Returns:
            Report type: '10-K', '10-Q', '8-K', or 'Unknown'
        """
        source_lower = source.lower()
        if '10k' in source_lower or '10-k' in source_lower:
            return '10-K'
        elif '10q' in source_lower or '10-q' in source_lower:
            return '10-Q'
        elif '8k' in source_lower or '8-k' in source_lower:
            return '8-K'
        return 'Unknown'


# Convenience functions for backward compatibility
def get_column_letter(idx: int) -> str:
    """Convert column index to Excel column letter."""
    return ExcelUtils.get_column_letter(idx)


def sanitize_sheet_name(name: str) -> str:
    """Sanitize string for Excel sheet name."""
    return ExcelUtils.sanitize_sheet_name(name)


def normalize_title_for_grouping(title: str) -> str:
    """Normalize title for grouping."""
    return ExcelUtils.normalize_title_for_grouping(title)
