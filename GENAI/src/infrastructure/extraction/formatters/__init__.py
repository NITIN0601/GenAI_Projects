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
    # Excel export with Index sheet
    'ExcelTableExporter',
    'get_excel_exporter',
    'reset_excel_exporter',
]

