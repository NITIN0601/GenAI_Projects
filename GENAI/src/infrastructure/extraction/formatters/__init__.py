"""
Table formatters for extraction results.

Provides utilities for formatting extracted tables into various formats.
"""

from src.infrastructure.extraction.formatters.table_formatter import (
    TableStructureFormatter,
    format_table_structure,
    format_extraction_tables,
)
from src.infrastructure.extraction.formatters.enhanced_formatter import (
    EnhancedTableFormatter,
    format_enhanced_table,
    format_all_tables_enhanced,
)
from src.infrastructure.extraction.formatters.metadata_extractor import (
    MetadataExtractor,
    extract_and_prepare_for_vectordb,
)
from src.infrastructure.extraction.formatters.excel_exporter import (
    ExcelTableExporter,
    get_excel_exporter,
    reset_excel_exporter,
)
from src.infrastructure.extraction.formatters.consolidated_exporter import (
    ConsolidatedExcelExporter,
    get_consolidated_exporter,
    reset_consolidated_exporter,
)
from src.infrastructure.extraction.formatters.header_detector import (
    HeaderDetector,
    detect_column_headers,
)
from src.infrastructure.extraction.formatters.date_utils import (
    DateUtils,
    parse_date_from_header,
    convert_to_quarter_format,
)
from src.infrastructure.extraction.formatters.excel_utils import (
    ExcelUtils,
    get_column_letter,
    sanitize_sheet_name,
    normalize_title_for_grouping,
)

__all__ = [
    # Basic formatting
    'TableStructureFormatter',
    'format_table_structure',
    'format_extraction_tables',
    # Enhanced formatting
    'EnhancedTableFormatter',
    'format_enhanced_table',
    'format_all_tables_enhanced',
    # Metadata extraction
    'MetadataExtractor',
    'extract_and_prepare_for_vectordb',
    # Excel export - single PDF
    'ExcelTableExporter',
    'get_excel_exporter',
    'reset_excel_exporter',
    # Excel export - consolidated
    'ConsolidatedExcelExporter',
    'get_consolidated_exporter',
    'reset_consolidated_exporter',
    # Header detection
    'HeaderDetector',
    'detect_column_headers',
    # Date utilities
    'DateUtils',
    'parse_date_from_header',
    'convert_to_quarter_format',
    # Excel utilities
    'ExcelUtils',
    'get_column_letter',
    'sanitize_sheet_name',
    'normalize_title_for_grouping',
]
