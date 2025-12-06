"""
Docling backend for PDF extraction.

Refactored from existing extract_page_by_page.py to use unified interface.
Includes all improvements: chunking, spanning headers, metadata extraction.
"""

import time
import logging
from pathlib import Path
from typing import Dict, Any, List

# Lazy import to avoid downloading models on module import
DocumentConverter = None
DocItemLabel = None
TableItem = None

def _ensure_docling_imported():
    """Lazy import of docling to avoid model downloads on module import."""
    global DocumentConverter, DocItemLabel, TableItem
    if DocumentConverter is None:
        from docling.document_converter import DocumentConverter as DC
        from docling_core.types.doc import DocItemLabel as DIL, TableItem as TI
        DocumentConverter = DC
        DocItemLabel = DIL
        TableItem = TI

from src.infrastructure.extraction.base import ExtractionBackend, ExtractionResult, BackendType
from src.infrastructure.embeddings.chunking import TableChunker
from src.utils.extraction_utils import PDFMetadataExtractor, DoclingHelper

logger = logging.getLogger(__name__)


class DoclingBackend(ExtractionBackend):
    """
    Docling extraction backend with all optimizations.
    
    Features:
    - Page-by-page processing
    - Intelligent chunking with overlap
    - Centered spanning headers
    - Multi-line header flattening
    - Complete metadata extraction
    """
    
    def __init__(
        self,
        chunk_size: int = 10,
        overlap: int = 3,
        flatten_headers: bool = False
    ):
        """
        Initialize Docling backend.
        
        Args:
            chunk_size: Rows per chunk
            overlap: Overlapping rows between chunks
            flatten_headers: Flatten multi-line headers
        """
        self.chunk_size = chunk_size
        self.overlap = overlap
        self.flatten_headers = flatten_headers
        self.chunker = TableChunker(
            chunk_size=chunk_size,
            overlap=overlap,
            flatten_headers=flatten_headers
        )
    
    def extract(self, pdf_path: str, **kwargs) -> ExtractionResult:
        """
        Extract tables from PDF using Docling.
        
        Args:
            pdf_path: Path to PDF file
            **kwargs: Additional options
            
        Returns:
            ExtractionResult with tables and metadata
        """
        # Lazy import docling when actually needed
        _ensure_docling_imported()
        
        start_time = time.time()
        result = ExtractionResult(
            backend=BackendType.DOCLING,
            pdf_path=pdf_path
        )
        
        try:
            # Convert PDF with Docling
            logger.info(f"Extracting {pdf_path} with Docling...")
            try:
                doc_result = DoclingHelper.convert_pdf(pdf_path)
            except Exception as e:
                # Log full error and re-raise to make failures visible
                logger.exception(f"Docling conversion failed for {pdf_path}: {e}")
                raise
            doc = doc_result.document
            
            # Extract tables
            tables = DoclingHelper.extract_tables(doc)
            logger.info(f"Found {len(tables)} tables")
            
            # Process each table
            all_chunks = []
            for i, table_item in enumerate(tables):
                try:
                    chunks = self._extract_table_chunks(table_item, pdf_path, doc, table_index=i)
                    all_chunks.extend(chunks)
                except Exception as e:
                    logger.error(f"Error extracting table {i + 1}: {e}")
                    result.warnings.append(f"Table {i + 1} extraction failed: {str(e)}")
            
            # Convert chunks to table dictionaries
            result.tables = [self._chunk_to_dict(chunk) for chunk in all_chunks]
            result.page_count = len(set(chunk.metadata.page_no for chunk in all_chunks))
            
            # Extract metadata
            result.metadata = self._extract_metadata(pdf_path, doc)
            
            # Calculate quality score (Docling is high quality)
            result.quality_score = 85.0  # Base score for Docling
            
        except Exception as e:
            logger.error(f"Docling extraction failed: {e}")
            result.error = str(e)
        
        result.extraction_time = time.time() - start_time
        logger.info(f"Extraction completed in {result.extraction_time:.2f}s")
        
        return result
    
    def _extract_table_chunks(self, table_item: TableItem, pdf_path: str, doc, table_index: int = 0) -> List:
        """Extract and chunk a single table."""
        from src.utils.extraction_utils import FootnoteExtractor
        
        # Get table text with doc argument to avoid deprecation warning
        if hasattr(table_item, 'export_to_markdown'):
            raw_table_text = table_item.export_to_markdown(doc=doc)
        else:
            raw_table_text = str(table_item.text)
        
        # Clean footnotes from row labels
        table_text, footnotes_map = FootnoteExtractor.clean_table_content(raw_table_text)
        
        # Get page number
        page_no = DoclingHelper.get_item_page(table_item)
        
        # Get better table title
        caption = DoclingHelper.extract_table_title(doc, table_item, table_index, page_no)
        
        # Create metadata with footnotes
        metadata = PDFMetadataExtractor.create_metadata(
            pdf_path=pdf_path,
            page_no=page_no,
            table_title=caption,
            table_index=table_index,
            footnote_references=list(set(fn for fns in footnotes_map.values() for fn in fns)) if footnotes_map else None
        )
        
        # Chunk table (use cleaned text for embeddings)
        chunks = self.chunker.chunk_table(table_text, metadata)
        
        # Store original (with footnotes) for reference
        for chunk in chunks:
            chunk._raw_content = raw_table_text
            chunk._footnotes_map = footnotes_map
        
        return chunks
    
    def _chunk_to_dict(self, chunk) -> Dict[str, Any]:
        """Convert TableChunk to dictionary."""
        result = {
            'content': chunk.content,  # Cleaned content without footnote refs
            'metadata': {
                'source_doc': chunk.metadata.source_doc,
                'page_no': chunk.metadata.page_no,
                'table_title': chunk.metadata.table_title,
                'year': chunk.metadata.year,
                'quarter': chunk.metadata.quarter,
                'report_type': chunk.metadata.report_type,
            }
        }
        
        # Add footnotes to metadata if present
        if hasattr(chunk.metadata, 'footnote_references') and chunk.metadata.footnote_references:
            result['metadata']['footnote_references'] = chunk.metadata.footnote_references
        
        # Store raw content with footnotes for reference
        if hasattr(chunk, '_raw_content'):
            result['raw_content'] = chunk._raw_content
        if hasattr(chunk, '_footnotes_map'):
            result['footnotes_map'] = chunk._footnotes_map
        
        return result
    
    def _extract_metadata(self, pdf_path: str, doc) -> Dict[str, Any]:
        """Extract document metadata."""
        filename = Path(pdf_path).name
        
        return {
            'filename': filename,
            'year': PDFMetadataExtractor.extract_year(filename),
            'quarter': PDFMetadataExtractor.extract_quarter(filename),
            'report_type': PDFMetadataExtractor.extract_report_type(filename),
            'file_hash': PDFMetadataExtractor.compute_file_hash(pdf_path)
        }
    
    def get_name(self) -> str:
        """Get backend name."""
        return "Docling"
    
    def get_backend_type(self) -> BackendType:
        """Get backend type."""
        return BackendType.DOCLING
    
    def is_available(self) -> bool:
        """Check if Docling is available."""
        try:
            import docling
            return True
        except ImportError:
            return False
    
    def get_priority(self) -> int:
        """Get priority (1 = highest)."""
        return 1
    
    def get_version(self) -> str:
        """Get Docling version."""
        try:
            import docling
            return docling.__version__
        except (ImportError, AttributeError) as e:
            logger.debug(f"Could not get Docling version: {e}")
            return "unknown"
    
    def supports_feature(self, feature: str) -> bool:
        """Check feature support."""
        supported = {
            'chunking', 'spanning_headers', 'multi_line_headers',
            'metadata_extraction', 'page_by_page'
        }
        return feature in supported
