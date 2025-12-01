"""
Backward compatibility wrapper for old import paths.

This module provides backward compatibility for code using old import paths.
New code should use the new paths directly.

OLD: from extraction.unified_extractor import UnifiedExtractor
NEW: from data_processing.extraction import UnifiedExtractor
"""

import warnings

# Import from new location
from data_processing.extraction import UnifiedExtractor

# Warn about deprecated import
warnings.warn(
    "Importing from 'extraction.unified_extractor' is deprecated. "
    "Use 'from data_processing.extraction import UnifiedExtractor' instead.",
    DeprecationWarning,
    stacklevel=2
)

__all__ = ['UnifiedExtractor']
