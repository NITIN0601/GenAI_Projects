"""
Constants for the Process step.

Shared constants used across process step modules.
"""

# File pattern for processed xlsx files
TABLE_FILE_PATTERN = "*_tables.xlsx"

# Excel number formats
CURRENCY_FORMAT = '$#,##0.00'
PERCENT_FORMAT = '0.00%'
NEGATIVE_CURRENCY_FORMAT = '$#,##0.00;[Red]($#,##0.00)'

# Table layout constants (per extracted Excel structure)
DEFAULT_HEADER_START_ROW = 13  # Headers typically start at row 13 in extracted Excel files
MAX_HEADER_SCAN_ROWS = 4  # Maximum header rows to check
MAX_SOURCE_MARKER_SCAN = 30  # Maximum rows to scan for "Source:" marker
KEY_VALUE_CHECK_ROWS = 7  # Rows to check when detecting key-value tables

# Key-value table detection labels
KEY_VALUE_LABELS = [
    'announcement date', 'amount per share', 'date paid', 'date to be paid',
    'shareholders of record', 'record date', 'ex-dividend date',
    'payment date', 'declaration date'
]
