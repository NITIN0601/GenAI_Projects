"""
CSV Exporter Constants.

Centralized constants for Excel to CSV migration.
Follows project patterns from metadata_labels.py.
"""

from enum import Enum
from typing import Dict, List


class CSVExportSettings:
    """CSV export configuration settings."""
    
    # File encoding
    ENCODING = 'utf-8-sig'  # UTF-8 with BOM for Excel compatibility
    
    # CSV format
    QUOTING_STYLE = 'minimal'  # Quote only fields with special chars
    LINE_TERMINATOR = '\n'
    
    # File naming
    INDEX_FILENAME = 'Index.csv'
    TABLE_FILENAME_PATTERN = '{sheet_id}.csv'
    MULTI_TABLE_FILENAME_PATTERN = '{sheet_id}_table_{table_index}.csv'
    
    # Default values for missing mandatory fields
    DEFAULT_TABLE_TITLE = '[Unknown Table]'
    DEFAULT_SOURCE = '[Unknown Source]'


class MetadataColumnMapping:
    """
    Mapping from original metadata keys to CSV-compatible column names.
    
    Uses underscores instead of spaces/parentheses for CSV compatibility.
    """
    
    # Original Index columns (preserved as-is for compatibility)
    INDEX_COLUMNS = [
        'Source',
        'PageNo', 
        'Table_ID',
        'Location_ID',
        'Section',
        'Table Title',
        'Link'
    ]
    
    # New metadata columns (extracted from table sheets)
    METADATA_COLUMNS = [
        'Table_Index',          # Position of table within sheet (1, 2, 3...)
        'Category_Parent',      # From "Category (Parent):"
        'Line_Items',           # From "Line Items:"
        'Product_Entity',       # From "Product/Entity:"
        'Column_Header',        # Combined L1/L2/L3 headers
        'Table_Title_Metadata', # From "Table Title:" in metadata block
        'Sources_Metadata',     # From "Source(s):" in metadata block
        'CSV_File'              # Path to exported CSV file
    ]
    
    # Full schema for enhanced Index
    ENHANCED_INDEX_COLUMNS = INDEX_COLUMNS + METADATA_COLUMNS
    
    # Mapping from metadata label prefixes to column names
    LABEL_TO_COLUMN: Dict[str, str] = {
        'Category (Parent):': 'Category_Parent',
        'Line Items:': 'Line_Items',
        'Product/Entity:': 'Product_Entity',
        'Column Header L1:': 'Column_Header_L1',
        'Column Header L2:': 'Column_Header_L2',
        'Column Header L3:': 'Column_Header_L3',
        'Year/Quarter:': 'Year_Quarter',
        'Table Title:': 'Table_Title_Metadata',
        'Source(s):': 'Sources_Metadata',
        'Source:': 'Sources_Metadata',
        'Sources:': 'Sources_Metadata',
    }


class TableDetectionPatterns:
    """Patterns for detecting table boundaries in sheets."""
    
    # Primary marker for table start
    TABLE_TITLE_MARKER = 'Table Title:'
    
    # Metadata row prefixes (in order of appearance)
    METADATA_PREFIXES = [
        '← Back to Index',
        'Category (Parent):',
        'Line Items:',
        'Product/Entity:',
        'Column Header L1:',
        'Column Header L2:',
        'Column Header L3:',
        'Year/Quarter:',
        'Table Title:',
        'Source(s):',
        'Source:',
        'Sources:',
    ]
    
    # Sub-table header patterns - these indicate start of a new data block
    # within a single logical table (e.g., sheet 105 with 7 sub-tables)
    # The first column cell should start with one of these patterns
    SUB_TABLE_HEADER_PATTERNS = [
        '$ in millions',
        '$ in billions',
        '$ in thousands',
        '($ in millions)',
        '($ in billions)',
        '($ in thousands)',
        # Without $ prefix
        'in millions',
        'in billions',
        'in thousands',
        '(in millions)',
        '(in billions)',
        '(in thousands)',
    ]
    
    # Sheets to skip during export
    SKIP_SHEETS = ['TOC', 'Index']
    
    # Minimum rows for a valid table
    MIN_DATA_ROWS = 1
    
    # Maximum metadata block size (to prevent runaway detection)
    MAX_METADATA_ROWS = 15
    
    # Minimum rows for a valid sub-table (data rows, excluding header)
    MIN_SUB_TABLE_DATA_ROWS = 2


class ExportStatus(Enum):
    """Status codes for export operations."""
    
    SUCCESS = 'success'
    PARTIAL_SUCCESS = 'partial_success'
    FAILED = 'failed'
    SKIPPED = 'skipped'
