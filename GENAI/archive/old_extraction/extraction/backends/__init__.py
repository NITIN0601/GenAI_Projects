"""
Backend registry and initialization.
"""

from data_processing.extraction.backends import (
    DoclingBackend,
    PyMuPDFBackend,
    PDFPlumberBackend,
    CamelotBackend
)

__all__ = ['DoclingBackend', 'PyMuPDFBackend', 'PDFPlumberBackend', 'CamelotBackend']
