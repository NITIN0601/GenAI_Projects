"""
Centralized constants for the GENAI system.

All magic numbers and configuration values should be defined here
for easy maintenance and configuration.
"""

# =============================================================================
# EXTRACTION CONSTANTS
# =============================================================================

# Default quality threshold for extraction (0-100)
EXTRACTION_MIN_QUALITY = 60.0

# Cache TTL in hours (168 = 1 week)
EXTRACTION_CACHE_TTL_HOURS = 168

# Maximum PDF file size in MB
EXTRACTION_MAX_SIZE_MB = 500

# Parallel extraction timeout in seconds (5 minutes)
EXTRACTION_PARALLEL_TIMEOUT = 300


# =============================================================================
# EXCEL EXPORT CONSTANTS
# =============================================================================

# Maximum Excel sheet name length (Excel limit is 31)
EXCEL_MAX_SHEET_NAME_LENGTH = 31

# Maximum items to display in summaries (source refs, row headers, etc.)
EXCEL_MAX_DISPLAY_ITEMS = 5

# Row limits for preview/sampling
EXCEL_PREVIEW_ROWS = 5
EXCEL_MAX_ROW_HEADERS_PREVIEW = 50

# Header row offset for checking sub-headers
EXCEL_HEADER_CHECK_OFFSET_MAX = 4


# =============================================================================
# TABLE PROCESSING CONSTANTS
# =============================================================================

# Maximum rows to scan for header detection in table merger
TABLE_MERGER_MAX_HEADER_SCAN_ROWS = 8

# Maximum columns to scan for data detection
TABLE_MERGER_MAX_COL_SCAN = 10

# Minimum year values needed to classify row as header
TABLE_MERGER_MIN_YEAR_COUNT_FOR_HEADER = 2

# Year string length for validation
YEAR_STRING_LENGTH = 4

# Default parallel workers for table processing
TABLE_MERGER_MAX_WORKERS = 4

# File pattern for processed table files
TABLE_FILE_PATTERN = "*_tables.xlsx"


# =============================================================================
# CONSOLIDATION CONSTANTS
# =============================================================================

# Year range for financial reports
CONSOLIDATION_YEAR_BASE = 2000
CONSOLIDATION_YEAR_MIN = 2000
CONSOLIDATION_YEAR_MAX = 2099

# Maximum search results for consolidation
CONSOLIDATION_TOP_K = 50


# =============================================================================
# QUALITY ASSESSMENT CONSTANTS
# =============================================================================

# Score thresholds
QUALITY_SCORE_MODERATE_TABLES = 15.0
QUALITY_SCORE_TEXT_GARBLED = 5.0

# Table count thresholds
QUALITY_TABLE_COUNT_MODERATE = 5

# Default backend confidence
QUALITY_DEFAULT_BACKEND_CONFIDENCE = 5.0


# =============================================================================
# HEADER DETECTION CONSTANTS
# =============================================================================

# Maximum rows to check after separator for header detection
HEADER_DETECTOR_MAX_ROWS_AFTER_SEPARATOR = 4


# =============================================================================
# TEXT PROCESSING CONSTANTS
# =============================================================================

# Maximum text length for title/caption truncation
TEXT_MAX_TITLE_LENGTH = 100

# Minimum text length for valid content
TEXT_MIN_VALID_LENGTH = 3

# Maximum text length for section names
TEXT_MAX_SECTION_LENGTH = 80

# Log truncation length
LOG_TRUNCATE_LENGTH = 50
