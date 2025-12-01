"""
Data Processing - Extraction module.

PDF extraction with multiple backends and unified interface.

Backends:
- Docling (best quality, recommended)
- PyMuPDF (fast, good quality)
- PDFPlumber (tables focus)
- Camelot (complex tables)

Usage:
    from data_processing.extraction import UnifiedExtractor
    
    extractor = UnifiedExtractor()  # Uses settings.EXTRACTION_BACKENDS
    result = extractor.extract("document.pdf")
"""

from data_processing.extraction.unified_extractor import UnifiedExtractor, extract_pdf
from data_processing.extraction.base import ExtractionResult, BackendType
from data_processing.extraction.strategy import ExtractionStrategy
from data_processing.extraction.quality import QualityAssessor

__all__ = [
    'UnifiedExtractor',
    'extract_pdf',
    'ExtractionResult',
    'BackendType',
    'ExtractionStrategy',
    'QualityAssessor',
]
