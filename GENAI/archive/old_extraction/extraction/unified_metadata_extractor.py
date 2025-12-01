"""
Backward compatibility wrapper for old import paths.

This module provides backward compatibility for code using old import paths.
New code should use the new paths directly.

OLD: from extraction.unified_metadata_extractor import UnifiedMetadataExtractor
NEW: from data_processing.ingestion import UnifiedMetadataExtractor
"""

import warnings

# Import from new location
from data_processing.ingestion.metadata_extractor import (
    UnifiedMetadataExtractor,
    extract_enhanced_metadata_unified
)

# Warn about deprecated import
warnings.warn(
    "Importing from 'extraction.unified_metadata_extractor' is deprecated. "
    "Use 'from data_processing.ingestion import UnifiedMetadataExtractor' instead.",
    DeprecationWarning,
    stacklevel=2
)

__all__ = ['UnifiedMetadataExtractor', 'extract_enhanced_metadata_unified']
