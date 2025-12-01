"""
Backward compatibility wrapper for extraction base classes.

This module re-exports from the new location for backward compatibility.
New code should use: from data_processing.extraction.base import ...
"""

from data_processing.extraction.base import (
    BackendType,
    ExtractionResult,
    ExtractionBackend,
    ExtractionError,
    BackendNotAvailableError,
    QualityThresholdError
)

__all__ = [
    'BackendType',
    'ExtractionResult',
    'ExtractionBackend',
    'ExtractionError',
    'BackendNotAvailableError',
    'QualityThresholdError',
]
