"""
Extraction backends - PDF extraction implementations.

Available backends:
- Docling: Best quality, recommended
- PyMuPDF: Fast, good quality
- PDFPlumber: Table focus
- Camelot: Complex tables
"""

from data_processing.extraction.backends.docling_backend import DoclingBackend
from data_processing.extraction.backends.pymupdf_backend import PyMuPDFBackend
from data_processing.extraction.backends.pdfplumber_backend import PDFPlumberBackend
from data_processing.extraction.backends.camelot_backend import CamelotBackend

__all__ = [
    'DoclingBackend',
    'PyMuPDFBackend',
    'PDFPlumberBackend',
    'CamelotBackend',
]
