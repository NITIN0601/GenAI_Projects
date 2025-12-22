"""
Table formatters for extraction results.

Provides utilities for parsing and formatting extracted tables.
For export functionality, see src.infrastructure.extraction.exporters.
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
from src.infrastructure.extraction.formatters.header_detector import (
    HeaderDetector,
    detect_column_headers,
)

# Re-exports from new locations for backward compatibility
from src.infrastructure.extraction.metadata_extractor import (
    MetadataExtractor,
    extract_and_prepare_for_vectordb,
)
from src.infrastructure.extraction.exporters.excel_exporter import (
    ExcelTableExporter,
    get_excel_exporter,
    reset_excel_exporter,
)
from src.infrastructure.extraction.consolidation.consolidated_exporter import (
    ConsolidatedExcelExporter,
    get_consolidated_exporter,
    reset_consolidated_exporter,
)
from src.utils.date_utils import (
    DateUtils,
    parse_date_from_header,
    convert_to_quarter_format,
)
from src.utils.excel_utils import (
    ExcelUtils,
    get_column_letter,
    sanitize_sheet_name,
    normalize_title_for_grouping,
)

__all__ = [
    # Core formatters
    'TableStructureFormatter',
    'format_table_structure',
    'format_extraction_tables',
    'EnhancedTableFormatter',
    'format_enhanced_table',
    'format_all_tables_enhanced',
    'HeaderDetector',
    'detect_column_headers',
    # Re-exports (backward compatibility)
    'MetadataExtractor',
    'extract_and_prepare_for_vectordb',
    'ExcelTableExporter',
    'get_excel_exporter',
    'reset_excel_exporter',
    'ConsolidatedExcelExporter',
    'get_consolidated_exporter',
    'reset_consolidated_exporter',
    'DateUtils',
    'parse_date_from_header',
    'convert_to_quarter_format',
    'ExcelUtils',
    'get_column_letter',
    'sanitize_sheet_name',
    'normalize_title_for_grouping',
]
