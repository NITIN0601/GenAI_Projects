"""
Data Processing - Ingestion module.

Handles chunking, metadata extraction, and preprocessing.

Components:
- Chunker: Table chunking with overlap
- Metadata Extractor: Enhanced metadata (21+ fields)
- Formatters: Table formatting
- Pipeline: Complete ingestion pipeline

Usage:
    from data_processing.ingestion import get_table_chunker, UnifiedMetadataExtractor
    
    chunker = get_table_chunker()
    metadata_extractor = UnifiedMetadataExtractor()
"""

from data_processing.ingestion.chunker import get_table_chunker, TableChunker
from data_processing.ingestion.metadata_extractor import (
    UnifiedMetadataExtractor,
    extract_enhanced_metadata_unified
)

__all__ = [
    'get_table_chunker',
    'TableChunker',
    'UnifiedMetadataExtractor',
    'extract_enhanced_metadata_unified',
]
