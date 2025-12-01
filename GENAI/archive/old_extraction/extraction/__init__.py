"""
Unified PDF extraction system.

Provides a single interface for PDF table extraction with:
- Multiple backends (Docling, PyMuPDF, pdfplumber, Camelot)
- Automatic fallback strategy
- Quality assessment
- Caching
- Table structure formatting
"""

from data_processing.extraction.base import (
    ExtractionBackend,
    ExtractionResult,
    BackendType,
    ExtractionError,
    BackendNotAvailableError,
    QualityThresholdError
)
from data_processing.extraction import UnifiedExtractor, extract_pdf
from extraction.table_formatter import (
    TableStructureFormatter,
    format_table_structure,
    format_extraction_tables
)
from extraction.enhanced_formatter import (
    EnhancedTableFormatter,
    format_enhanced_table,
    format_all_tables_enhanced
)
from data_processing.extraction.backends import DoclingBackend, PyMuPDFBackend
from data_processing.extraction.quality import QualityAssessor
from data_processing.extraction.cache import ExtractionCache
from data_processing.extraction.strategy import ExtractionStrategy

__version__ = "1.0.0"

__all__ = [
    # Main interface
    'UnifiedExtractor',
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
    
    # Components
    'ExtractionStrategy',
    'QualityAssessor',
    'ExtractionCache',
    
    # Base classes
    'ExtractionBackend',
    'ExtractionResult',
    'BackendType',
    
    # Exceptions
    'ExtractionError',
    'BackendNotAvailableError',
    'QualityThresholdError',
]
