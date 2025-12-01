"""
Data Processing - Main module.

Consolidates all data processing components:
- Extraction: PDF extraction
- Ingestion: Chunking, metadata, preprocessing
- Scrapers: Web scraping utilities
"""

from data_processing.extraction import UnifiedExtractor
from data_processing.ingestion import get_table_chunker, UnifiedMetadataExtractor

__all__ = [
    'UnifiedExtractor',
    'get_table_chunker',
    'UnifiedMetadataExtractor',
]
