"""
Extraction backends - PDF extraction implementations.

Available backends:
- Docling: Best quality, recommended
- PyMuPDF: Fast, good quality
- PDFPlumber: Table focus
- Camelot: Complex tables
- Unstructured: Multi-format support
"""

from src.infrastructure.extraction.backends.docling_backend import DoclingBackend
from src.infrastructure.extraction.backends.pymupdf_backend import PyMuPDFBackend
from src.infrastructure.extraction.backends.pdfplumber_backend import PDFPlumberBackend
from src.infrastructure.extraction.backends.camelot_backend import CamelotBackend
from src.infrastructure.extraction.backends.unstructured_backend import UnstructuredBackend

# Alias for convenience
PdfPlumberBackend = PDFPlumberBackend

__all__ = [
    'DoclingBackend',
    'PyMuPDFBackend',
    'PDFPlumberBackend',
    'PdfPlumberBackend',  # Alias
    'CamelotBackend',
    'UnstructuredBackend',
]
