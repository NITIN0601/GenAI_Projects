"""
Docling backend for PDF extraction.

Refactored from existing extract_page_by_page.py to use unified interface.
Includes all improvements: chunking, spanning headers, metadata extraction.
"""

import time
from collections import defaultdict
from pathlib import Path
from typing import Dict, Any, List, TYPE_CHECKING

from src.utils import get_logger

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

logger = get_logger(__name__)


class DoclingBackend(ExtractionBackend):
    """
    Docling extraction backend - extracts COMPLETE tables from PDFs.
    
    Features:
    - Page-by-page processing
    - Complete table extraction (no chunking - chunking is done in embedding stage)
    - Centered spanning headers
    - Multi-line header flattening
    - Complete metadata extraction
    
    Note: Chunking for RAG/embeddings is handled separately in the embedding pipeline,
    not during extraction. This ensures complete tables are available for Excel export.
    """
    
    def __init__(self, flatten_headers: bool = False):
        """
        Initialize Docling backend for complete table extraction.
        
        Args:
            flatten_headers: Flatten multi-line headers
        """
        self.flatten_headers = flatten_headers
        # Use very large chunk_size to pass tables through without splitting
        # Actual chunking for embeddings happens in the embed pipeline
        self.chunker = TableChunker(
            chunk_size=100000,  # Effectively no chunking
            overlap=0,
            flatten_headers=flatten_headers
        )
        logger.info("DoclingBackend initialized - extracting complete tables")
    
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
            
            # Group tables by page number for proper indexing (page_1, page_2, etc.)
            page_table_counts = defaultdict(int)  # Track how many tables per page
            
            # Process each table
            all_chunks = []
            for i, table_item in enumerate(tables):
                try:
                    # Get page number for this table
                    page_no = DoclingHelper.get_item_page(table_item)
                    
                    # Increment count for this page and get table index on this page
                    page_table_counts[page_no] += 1
                    table_index_on_page = page_table_counts[page_no]
                    
                    # Pass both global index and page-specific index
                    chunks = self._extract_table_chunks(
                        table_item, pdf_path, doc, 
                        table_index=i,
                        page_no=page_no,
                        table_index_on_page=table_index_on_page
                    )
                    all_chunks.extend(chunks)
                except Exception as e:
                    logger.error(f"Error extracting table {i + 1}: {e}")
                    result.warnings.append(f"Table {i + 1} extraction failed: {str(e)}")
            
            # Convert chunks to table dictionaries
            result.tables = [self._chunk_to_dict(chunk) for chunk in all_chunks]
            result.page_count = len(set(chunk.metadata.page_no for chunk in all_chunks))
            
            # Extract metadata
            result.metadata = self._extract_metadata(pdf_path, doc)
            
            # Note: quality_score is computed by QualityAssessor in strategy.py
            # Not setting it here to avoid confusion with actual computed score
            
        except Exception as e:
            logger.error(f"Docling extraction failed: {e}")
            result.error = str(e)
        
        result.extraction_time = time.time() - start_time
        logger.info(f"Extraction completed in {result.extraction_time:.2f}s")
        
        return result
    
    def _extract_table_chunks(
        self, 
        table_item,  # TableItem - lazily imported
        pdf_path: str, 
        doc, 
        table_index: int = 0,
        page_no: int = None,
        table_index_on_page: int = None
    ) -> List:
        """
        Extract and chunk a single table.
        
        Args:
            table_item: Docling table item
            pdf_path: Path to source PDF
            doc: Docling document
            table_index: Global index of table in document (0-based)
            page_no: Page number (1-indexed)
            table_index_on_page: Index of table on this specific page (1-indexed)
        """
        from src.utils.extraction_utils import FootnoteExtractor, CurrencyValueCleaner
        
        # Get page number early (needed for spanning header detection)
        if page_no is None:
            page_no = DoclingHelper.get_item_page(table_item)
        
        # Get table text with doc argument to avoid deprecation warning
        if hasattr(table_item, 'export_to_markdown'):
            raw_table_text = table_item.export_to_markdown(doc=doc)
        else:
            raw_table_text = str(table_item.text)
        
        # === POST-PROCESS: Detect and add missing spanning headers ===
        # If the table's first row doesn't look like a spanning header (date/period),
        # check if there's a preceding TEXT item that should be the spanning header.
        def table_has_spanning_header(md_text: str) -> bool:
            """Check if table already has a spanning date/period header row."""
            import re
            lines = md_text.strip().split('\n')
            if not lines:
                return True  # Empty - nothing to add
            
            first_row = lines[0]
            # Check for date patterns in first row
            has_year = bool(re.search(r'\b20[0-3]\d\b', first_row))
            has_period = any(ind in first_row.lower() for ind in 
                           ['ended', 'ending', 'months', 'as of', 'at '])
            return has_year and has_period
        
        def count_columns(md_text: str) -> int:
            """Count columns in markdown table."""
            lines = md_text.strip().split('\n')
            for line in lines:
                if '|' in line and not all(c in '|-: ' for c in line):
                    return line.count('|') - 1  # Pipes minus outer ones
            return 0
        
        # Check if table needs a spanning header
        if not table_has_spanning_header(raw_table_text):
            # Try to find a preceding TEXT item that's the missing header
            preceding_header = DoclingHelper.find_preceding_spanning_header(
                doc, table_item, page_no
            )
            if preceding_header:
                num_cols = count_columns(raw_table_text)
                raw_table_text = DoclingHelper.prepend_spanning_header(
                    raw_table_text, preceding_header, num_cols
                )
                logger.debug(f"Prepended spanning header: {preceding_header[:50]}...")
        
        # Also try to get HTML for better structure preservation
        html_content = None
        if hasattr(table_item, 'export_to_html'):
            try:
                html_content = table_item.export_to_html(doc=doc)
            except Exception as e:
                logger.debug(f"HTML export failed, using markdown: {e}")
        
        # Clean currency values (handle split cells like "$10,207 $ 2,762")
        # This must happen BEFORE footnote cleaning
        table_text_cleaned = CurrencyValueCleaner.clean_table_rows(raw_table_text)
        
        # Clean footnotes from row labels
        table_text, footnotes_map = FootnoteExtractor.clean_table_content(table_text_cleaned)
        
        # Default table_index_on_page to global index if not provided
        if table_index_on_page is None:
            table_index_on_page = table_index + 1
        
        # Generate table_id with format: page_tableIndexOnPage (e.g., "7_1", "7_2")
        filename = Path(pdf_path).stem
        table_id = f"{filename}_p{page_no}_{table_index_on_page}"
        
        # Get better table title
        caption = DoclingHelper.extract_table_title(doc, table_item, table_index, page_no)
        
        # Get section name (e.g., "Institutional Securities", "Wealth Management")
        section_name = DoclingHelper.extract_section_name(doc, table_item, page_no)
        
        # Create metadata with footnotes, section, and page-based table_id
        metadata = PDFMetadataExtractor.create_metadata(
            pdf_path=pdf_path,
            page_no=page_no,
            table_title=caption,
            table_index=table_index,
            table_id=table_id,  # Page-based ID: e.g., "10q0624_p7_1"
            table_index_on_page=table_index_on_page,  # NEW: index on this page
            section_name=section_name,
            footnote_references=list(set(fn for fns in footnotes_map.values() for fn in fns)) if footnotes_map else None
        )
        
        # Chunk table (use cleaned text for embeddings)
        chunks = self.chunker.chunk_table(table_text, metadata)
        
        # Store original content for reference
        for chunk in chunks:
            chunk._raw_content = raw_table_text
            chunk._footnotes_map = footnotes_map
            # Store HTML if available for structured queries
            if html_content:
                chunk._html_content = html_content
        
        return chunks
    
    def _chunk_to_dict(self, chunk) -> Dict[str, Any]:
        """Convert TableChunk to dictionary."""
        result = {
            'content': chunk.content,  # Cleaned content without footnote refs
            'metadata': {
                'source_doc': chunk.metadata.source_doc,
                'page_no': chunk.metadata.page_no,
                'table_id': getattr(chunk.metadata, 'table_id', '') or '',  # Page-based ID
                'table_index_on_page': getattr(chunk.metadata, 'table_index_on_page', None),  # Index on page
                'table_title': chunk.metadata.table_title,
                'section_name': getattr(chunk.metadata, 'section_name', '') or '',
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
        
        # Store HTML content for structured table queries
        if hasattr(chunk, '_html_content'):
            result['html_content'] = chunk._html_content
        
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
