"""
Unified PDF extraction system.

Enterprise-grade PDF extraction with multiple backends, automatic fallback,
quality assessment, and caching.

Main Components:
- Extractor: Main extraction interface
- Backends: Multiple extraction backends (Docling, PyMuPDF, PDFPlumber, Camelot)
- Strategy: Intelligent fallback mechanism
- Quality: Quality assessment
- Cache: Result caching
- Formatters: Table formatting utilities

Example:
    >>> from src.infrastructure.extraction import Extractor, extract_pdf
    >>> 
    >>> # Quick extraction
    >>> result = extract_pdf("document.pdf")
    >>> 
    >>> # Advanced usage
    >>> extractor = Extractor(backends=["docling", "pymupdf"])
    >>> result = extractor.extract("document.pdf")
    >>> print(f"Found {len(result.tables)} tables")
"""

from src.infrastructure.extraction.base import (
    ExtractionBackend,
    ExtractionResult,
    BackendType,
    ExtractionError,
    BackendNotAvailableError,
    QualityThresholdError
)
from src.infrastructure.extraction.extractor import UnifiedExtractor as Extractor, extract_pdf
from src.infrastructure.extraction.formatters.table_formatter import (
    TableStructureFormatter,
    format_table_structure,
    format_extraction_tables
)
from src.infrastructure.extraction.formatters.enhanced_formatter import (
    EnhancedTableFormatter,
    format_enhanced_table,
    format_all_tables_enhanced
)
from src.infrastructure.extraction.backends import (
    DoclingBackend,
    PyMuPDFBackend,
    PDFPlumberBackend,
    CamelotBackend,
    UnstructuredBackend
)
from src.infrastructure.extraction.quality import QualityAssessor
from src.infrastructure.extraction.cache import ExtractionCache
from src.infrastructure.extraction.strategy import ExtractionStrategy
from src.infrastructure.extraction.consolidation import (
    MultiYearTableConsolidator,
    QuarterlyTableConsolidator,
    get_multi_year_consolidator,
    get_quarterly_consolidator,
    ConsolidatedExcelExporter,
    get_consolidated_exporter,
)
from src.infrastructure.extraction.exporters import (
    ExcelTableExporter,
    get_excel_exporter,
    ReportExporter,
    get_report_exporter,
)

__version__ = "2.0.0"

__all__ = [
    # Main interface
    'Extractor',
    'extract_pdf',
    
    # Table formatting
    'TableStructureFormatter',
    'format_table_structure',
    'format_extraction_tables',
    'EnhancedTableFormatter',
    'format_enhanced_table',
    'format_all_tables_enhanced',
    
    # Backends
    'DoclingBackend',
    'PyMuPDFBackend',
    'PDFPlumberBackend',
    'CamelotBackend',
    'UnstructuredBackend',
    
    # Components
    'ExtractionStrategy',
    'QualityAssessor',
    'ExtractionCache',
    
    # Table consolidation
    'MultiYearTableConsolidator',
    'QuarterlyTableConsolidator',
    'get_multi_year_consolidator',
    'get_quarterly_consolidator',
    'ConsolidatedExcelExporter',
    'get_consolidated_exporter',
    
    # Exporters
    'ExcelTableExporter',
    'get_excel_exporter',
    'ReportExporter',
    'get_report_exporter',
    
    # Base classes
    'ExtractionBackend',
    'ExtractionResult',
    'BackendType',
    
    # Exceptions
    'ExtractionError',
    'BackendNotAvailableError',
    'QualityThresholdError',
]
