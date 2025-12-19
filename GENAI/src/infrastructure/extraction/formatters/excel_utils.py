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
        
        Removes footnote markers and extra whitespace.
        
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
        
        # Remove footnote patterns like (1), [2], {3}
        label = re.sub(r'[\(\[\{]\d+[\)\]\}]', ' ', label)
        label = re.sub(r'\*+', ' ', label)
        label = re.sub(r'[:\.]$', '', label)
        label = re.sub(r'\s+', ' ', label)
        
        return label.lower().strip()
    
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
