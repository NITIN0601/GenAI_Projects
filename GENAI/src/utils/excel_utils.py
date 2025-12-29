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
    
    # Known OCR broken words from Docling PDF extraction (space inserted mid-word)
    OCR_FIXES = {
        'Manageme nt': 'Management',
        'manageme nt': 'management',
        'Institutio nal': 'Institutional',
        'institutio nal': 'institutional',
        'Investme nt': 'Investment',
        'investme nt': 'investment',
        'Securitie s': 'Securities',
        'securitie s': 'securities',
        'Advisor-led': 'Advisor-Led',
        'Self-directed': 'Self-Directed',
    }
    
    @staticmethod
    def fix_ocr_broken_words(text: str) -> str:
        """
        Fix known OCR broken words from Docling PDF extraction.
        
        Handles cases like:
        - 'Manageme nt' -> 'Management' (space inserted mid-word)
        - 'Advisor-led' -> 'Advisor-Led' (capitalization)
        
        Args:
            text: Text to fix
            
        Returns:
            Fixed text
        """
        if not text:
            return text
        
        result = text
        for broken, fixed in ExcelUtils.OCR_FIXES.items():
            result = result.replace(broken, fixed)
        return result
    
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
        
        # First fix OCR broken words
        result = ExcelUtils.fix_ocr_broken_words(title)
        
        result = result.lower().strip()
        
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
        Normalizes punctuation, dashes, and ampersands for consistent matching.
        
        Handles patterns like:
        - 'Cash and Cash Equivalents 1 :' -> 'cash and cash equivalents'
        - 'Securities purchased under agreements to resell 3:' -> 'securities purchased...'
        - 'Customer receivables and Other 1,10 :' -> 'customer receivables and other'
        - 'Total assets (1)(2)' -> 'total assets'
        - 'Net income¹²' -> 'net income'
        - 'Fees & Commissions' -> 'fees and commissions'
        - 'Long–term' (en-dash) -> 'long-term' (hyphen)
        - 'Revenue (a)(b)' -> 'revenue'
        
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
        
        # Normalize Unicode dashes to ASCII hyphen
        # en-dash (–), em-dash (—), minus sign (−), etc.
        dash_chars = ['–', '—', '−', '‐', '‑', '―']
        for dash in dash_chars:
            label = label.replace(dash, '-')
        
        # Normalize ampersand to "and"
        label = re.sub(r'\s*&\s*', ' and ', label)
        
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
        # Pattern: Parenthesized numbers: "(1)" or "(1)(2)"
        label = re.sub(r'\s*\(\d+\)\s*', ' ', label)
        # Pattern: Parenthesized letters: "(a)" or "(a)(b)"
        label = re.sub(r'\s*\([a-zA-Z]\)\s*', ' ', label)
        # Pattern: Bracketed: "[1]" or "[2]"
        label = re.sub(r'\s*\[\d+\]\s*', ' ', label)
        # Pattern: Braced: "{1}" or "{2}"
        label = re.sub(r'\s*\{\d+\}\s*', ' ', label)
        # Pattern: Asterisks
        label = re.sub(r'\*+', ' ', label)
        # Pattern: Trailing colon, period, or comma
        label = re.sub(r'[:,\.]+\s*$', '', label)
        # Normalize multiple spaces
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
        # Be CONSERVATIVE to avoid false positives on meaningful text like "Level 2", "Tier 1"
        
        # === NEW: Handle footnotes BEFORE % symbol ===
        # Pattern: Footnote number attached to word before %: "engagement1 %" → "engagement %"
        # This handles cases like "engagement1 %Proud" from PDF where 1 is a superscript footnote
        text = re.sub(r'([a-zA-Z])(\d{1,2})\s+(%)', r'\1 \3', text)
        # Pattern: Footnote number with space before %: "officer 2 %" → "officer %"  
        # But be careful not to match "Level 2" which is valid
        text = re.sub(r'([a-zA-Z])\s+(\d{1,2})\s+(%)', r'\1 \3', text)
        # Pattern: Comma-separated footnotes before %: "officer2,3 %" → "officer %"
        text = re.sub(r'([a-zA-Z])(\d{1,2}(?:,\s*\d{1,2})*)\s+(%)', r'\1 \3', text)
        
        # === NEW: Handle trailing single digit footnotes (1-3) ===
        # These are the most common footnote markers, safe to remove at end of string
        # Pattern: Trailing single digit 1-3 at end: "diverse 3" → "diverse"
        text = re.sub(r'\s+[123]\s*$', '', text)
        # Pattern: Attached single digit 1-3 at end: "diverse3" → "diverse"  
        text = re.sub(r'([a-zA-Z])[123]\s*$', r'\1', text)
        
        # Pattern: Footnote number BEFORE parenthetical unit: "assets 2 (in billions)" → "assets (in billions)"
        text = re.sub(r'\s+\d+\s*(\(in\s+[^)]+\))', r' \1', text)
        # Pattern: Footnote number followed by comma BEFORE parenthetical: "assets 2, (in" → "assets (in"
        text = re.sub(r'\s+\d+,\s*(\(in\s+[^)]+\))', r' \1', text)
        # Pattern: Trailing comma after number at end: " 2," or " 3," → remove
        text = re.sub(r'\s+\d+,\s*$', '', text)
        # Pattern: Trailing comma-separated numbers (clear footnote): " 2,3" or " 2, 3" or " 2,3,4"
        text = re.sub(r'\s+\d+(?:,\s*\d+)+\s*$', '', text)
        # Pattern: Just trailing comma at end (leftover): "offerings," → "offerings"
        text = re.sub(r',\s*$', '', text)
        # Pattern: Attached numbers with comma: "Offering2," or "ROTCE2,3" or "ROTCE2, 3"
        text = re.sub(r'([a-zA-Z])\d+(?:,\s*\d+)*,?\s*$', r'\1', text)
        # Pattern: Numbers attached DIRECTLY to text (no space) at end: "Capital Ratios9" → "Capital Ratios"
        # This catches "Ratios9" but NOT "Level 2" (has space)
        text = re.sub(r'([a-zA-Z])\d+\s*$', r'\1', text)
        # Pattern: Trailing numbers before colon: "Text 1 :" or "Text 1,10 :"
        text = re.sub(r'\s+[\d,]+\s*:\s*$', '', text)
        # Pattern: Multiple trailing numbers (clear footnote): " 1 2 3" but NOT single " 2"
        text = re.sub(r'\s+\d+(?:\s+\d+)+\s*$', '', text)
        # Pattern: Parenthesized footnote numbers only: "(1)" but NOT "(in millions)"
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
    def parse_currency_to_float(val_str: str):
        """
        Parse a currency string to a float.
        
        Handles:
        - '$12.7' → 12.7
        - '$1,234.56' → 1234.56
        - '$(5.2)' → -5.2 (negative)
        - '(1,234)' → -1234.0 (negative without $)
        
        DOES NOT convert percentages - they stay as strings for Excel formatting:
        - '12.5%' → None (stays as '12.5%' string)
        
        Args:
            val_str: String value to parse
            
        Returns:
            Float if currency/number, None otherwise
        """
        import re
        
        if not val_str or not isinstance(val_str, str):
            return None
        
        val_str = val_str.strip()
        if not val_str:
            return None
        
        # Skip if it's a date-like string (e.g., "March 31, 2024")
        if re.search(r'(January|February|March|April|May|June|July|August|September|October|November|December)', val_str, re.IGNORECASE):
            return None
        
        # Skip percentages - they should stay as strings for Excel formatting
        # "34 %" or "34%" should NOT be converted to 0.34
        if '%' in val_str:
            return None
        
        # Check for negative (parentheses)
        is_negative = False
        if val_str.startswith('(') and val_str.endswith(')'):
            is_negative = True
            val_str = val_str[1:-1].strip()
        
        # Check for negative with $ inside parens: $(123)
        if val_str.startswith('$(') and val_str.endswith(')'):
            is_negative = True
            val_str = val_str[2:-1].strip()
        
        # Remove dollar sign
        has_dollar = '$' in val_str
        val_str = val_str.replace('$', '').strip()
        
        # Remove commas
        val_str = val_str.replace(',', '')
        
        # Remove leading/trailing dashes that are placeholders
        if val_str in ['-', '—', '–', '']:
            return None
        
        # Skip if it looks like a plain year (2020-2030) without currency markers
        # Only parse as currency if had $, (), or commas
        if not has_dollar and not is_negative:
            try:
                year_val = float(val_str)
                if 2000 <= year_val <= 2099 and year_val == int(year_val):
                    return None  # Don't parse years as currency
            except ValueError:
                pass
        
        # Try to parse as float
        try:
            result = float(val_str)
            if is_negative:
                result = -result
            return result
        except ValueError:
            return None
    
    @staticmethod
    def clean_cell_value(val):
        """
        Clean a data cell value. Returns float for currency/numbers, string otherwise.
        
        Handles:
        - Currency: '$12.7' → 12.7 (float)
        - Negatives: '$(5.2)' → -5.2 (float)
        - Year floats: 2024.0 → 2024 (int)
        - NaN values → ''
        
        Args:
            val: Cell value (string, int, float, or NaN)
            
        Returns:
            Float for currency/numbers, string otherwise
        """
        import pandas as pd
        
        if pd.isna(val):
            return ''
        
        # Already a number - keep as-is but handle year floats
        if isinstance(val, (int, float)):
            if isinstance(val, float):
                # Year floats (2024.0 → 2024)
                if val == int(val) and 2000 <= val <= 2099:
                    return int(val)
                # Other whole numbers
                if val == int(val):
                    return int(val)
            return val
        
        val_str = str(val).strip()
        
        # Try to parse as currency/number
        parsed = ExcelUtils.parse_currency_to_float(val_str)
        if parsed is not None:
            return parsed
        
        # Clean year floats in strings (e.g., "2024.0" → "2024")
        val_str = ExcelUtils.clean_year_string(val_str)
        
        return val_str
    
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
