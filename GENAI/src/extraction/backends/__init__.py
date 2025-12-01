"""
Extraction backends - PDF extraction implementations.

Available backends:
- Docling: Best quality, recommended
- PyMuPDF: Fast, good quality
- PDFPlumber: Table focus
- Camelot: Complex tables
"""

from src.extraction.backends.docling_backend import DoclingBackend
from src.extraction.backends.pymupdf_backend import PyMuPDFBackend
from src.extraction.backends.pdfplumber_backend import PDFPlumberBackend
from src.extraction.backends.camelot_backend import CamelotBackend

__all__ = [
    'DoclingBackend',
    'PyMuPDFBackend',
    'PDFPlumberBackend',
    'CamelotBackend',
]
