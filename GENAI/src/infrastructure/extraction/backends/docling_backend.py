"""
Docling backend for PDF extraction.

Refactored from existing extract_page_by_page.py to use unified interface.
Includes all improvements: chunking, spanning headers, metadata extraction.

100% LOCAL OPERATION (OFFLINE MODE):
- All models loaded from src/model/doclingPackage/
- No internet downloads (HF_HUB_OFFLINE=1, TRANSFORMERS_OFFLINE=1)
- Windows/Linux: RapidOCR with local ONNX models
- macOS: OcrMac (Apple Vision framework)
"""

__version__ = "1.0.0"
__author__ = "dundaymo"

import os
import time
import logging
from collections import defaultdict
from pathlib import Path
from typing import Dict, Any, List, TYPE_CHECKING

from functools import lru_cache

from src.utils import get_logger

logger = get_logger(__name__)


# Lazy import using @lru_cache to avoid downloading models on module import
@lru_cache(maxsize=1)
def _get_docling_imports():
    """
    Lazy import of docling to avoid model downloads on module import.
    Uses @lru_cache for thread-safe singleton pattern.
    
    WINDOWS OFFLINE MODE:
    - Auto-detects local models in src/model/doclingPackage/
    - Sets DOCLING_LOCAL_MODEL_DIR for extraction_utils to use
    - Calls _ensure_docling_imported() which configures RapidOCR offline
    """
    # Auto-detect local model bundle in the repo
    repo_root = Path(__file__).resolve().parents[4]
    local_model_path = repo_root / 'src' / 'model' / 'doclingPackage'
    
    # Set OFFLINE MODE environment variables to prevent any network downloads
    if local_model_path.exists():
        if os.environ.get('DOCLING_LOCAL_MODEL_DIR') is None:
            os.environ['DOCLING_LOCAL_MODEL_DIR'] = str(local_model_path)
        # Force offline mode for HuggingFace and Transformers
        os.environ['HF_HUB_OFFLINE'] = '1'
        os.environ['TRANSFORMERS_OFFLINE'] = '1'
        
        # RapidOCR offline mode (Windows/Linux):
        # - Disable visualization to prevent font download attempts
        # - Set local ONNX model paths if they exist
        import platform
        if platform.system() != 'Darwin':  # Not macOS (macOS uses OcrMac)
            os.environ['RAPIDOCR_DISABLE_VIS'] = '1'  # Disable visualization
            # Check for local RapidOCR models
            rapidocr_models = local_model_path / 'rapidocr'
            if rapidocr_models.exists():
                os.environ['RAPIDOCR_MODEL_DIR'] = str(rapidocr_models)
                logging.getLogger(__name__).info(f" RapidOCR OFFLINE: Using local ONNX models")
        
        logging.getLogger(__name__).info(f" OFFLINE MODE: Using local Docling models from: {local_model_path}")
    
    # Now import the specific symbols we need
    from docling.document_converter import DocumentConverter
    from docling_core.types.doc import DocItemLabel, TableItem
    return DocumentConverter, DocItemLabel, TableItem


from src.infrastructure.extraction.base import ExtractionBackend, ExtractionResult, BackendType
from src.infrastructure.embeddings.chunking import TableChunker
from src.infrastructure.extraction.helpers import DoclingHelper
from src.utils.extraction_utils import PDFMetadataExtractor


# =============================================================================
# MODULE-LEVEL HELPER FUNCTIONS (extracted from _extract_table_chunks)
# =============================================================================

def _clean_cell_internal_duplicate(cell_text: str) -> str:
    """Remove duplicated text within a single cell (e.g., 'Text A Text A' -> 'Text A')."""
    cell_stripped = cell_text.strip()
    if not cell_stripped or len(cell_stripped) < 10:
        return cell_text  # Too short to have meaningful duplicate
    
    # Check if cell contains the same text twice
    half_len = len(cell_stripped) // 2
    first_half = cell_stripped[:half_len].strip()
    second_half = cell_stripped[half_len:].strip()
    
    if first_half and first_half == second_half:
        # Return only the first half, preserving original spacing
        leading_space = len(cell_text) - len(cell_text.lstrip())
        return ' ' * leading_space + first_half
    
    return cell_text


def clean_row_header_duplicates(md_text: str) -> str:
    """
    Remove duplicate row header cells caused by Docling's colspan handling.
    
    Handles two patterns:
    1. Adjacent cells: | Text | Text | $100 | → | Text |  | $100 |
    2. Within a cell:  | Text Text | $100 | → | Text |  | $100 |
    
    Only affects the first column (row headers). Data columns are never touched.
    """
    lines = md_text.split('\n')
    cleaned_lines = []
    
    for line in lines:
        # Skip non-table lines and separator rows
        if '|' not in line or all(c in '|-: ' for c in line.strip()):
            cleaned_lines.append(line)
            continue
        
        cells = line.split('|')
        
        # Need at least 3 cells (empty + first col + second col + ...)
        if len(cells) < 4:
            cleaned_lines.append(line)
            continue
        
        first_cell = cells[1].strip()
        second_cell = cells[2].strip() if len(cells) > 2 else ''
        
        # Pattern 1: Check for duplicated text WITHIN the first cell
        cleaned_first = _clean_cell_internal_duplicate(cells[1])
        if cleaned_first != cells[1]:
            cells[1] = cleaned_first
            cells.insert(2, ' ')
            logger.debug(f"Cleaned internal duplicate: '{first_cell[:40]}...'")
        # Pattern 2: Check for adjacent cells with identical content
        elif (first_cell and 
              second_cell == first_cell and 
              len(first_cell) > 3 and 
              not first_cell.replace(',', '').replace('.', '').replace('$', '').replace('%', '').isdigit()):
            cells[2] = ' '
            logger.debug(f"Cleaned duplicate row header: '{first_cell[:40]}...'")
        
        cleaned_lines.append('|'.join(cells))
    
    return '\n'.join(cleaned_lines)


def _table_has_spanning_header(md_text: str) -> bool:
    """Check if table already has a spanning date/period header row."""
    import re
    lines = md_text.strip().split('\n')
    if not lines:
        return True  # Empty - nothing to add
    
    first_row = lines[0]
    has_year = bool(re.search(r'\b20[0-3]\d\b', first_row))
    has_period = any(ind in first_row.lower() for ind in 
                   ['ended', 'ending', 'months', 'as of', 'at '])
    return has_year and has_period


def _count_columns(md_text: str) -> int:
    """Count columns in markdown table."""
    lines = md_text.strip().split('\n')
    for line in lines:
        if '|' in line and not all(c in '|-: ' for c in line):
            return line.count('|') - 1  # Pipes minus outer ones
    return 0


class DoclingBackend(ExtractionBackend):
    """
    Docling extraction backend - extracts COMPLETE tables from PDFs.
    
    100% LOCAL OPERATION (OFFLINE MODE):
    - All models loaded from src/model/doclingPackage/
    - No internet downloads (HF_HUB_OFFLINE=1, TRANSFORMERS_OFFLINE=1)
    - English language support ✓
    
    Models Used (All Local):
    1. Layout Model: docling-layout-heron (model.safetensors ~220MB)
    2. TableFormer: model.onnx for table structure detection
    3. RapidOCR: PP-OCRv4 ONNX models (det, rec, cls) for text recognition
    
    Platform-Specific OCR:
    - Windows/Linux: RapidOCR with local ONNX models (visualization disabled)
    - macOS: OcrMac (Apple Vision framework)
    
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
        from config.settings import settings
        
        self.flatten_headers = flatten_headers
        # Use very large chunk_size to pass tables through without splitting
        # Actual chunking for embeddings happens in the embed pipeline
        self.chunker = TableChunker(
            chunk_size=settings.DOCLING_CHUNK_SIZE,  # Configurable via .env
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
        # Validate input file exists
        pdf_file = Path(pdf_path)
        if not pdf_file.exists():
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")
        if not pdf_file.is_file():
            raise ValueError(f"Path is not a file: {pdf_path}")
        
        # Lazy import docling when actually needed (uses lru_cache for efficiency)
        DocumentConverter, DocItemLabel, TableItem = _get_docling_imports()
        
        start_time = time.time()
        result = ExtractionResult(
            backend=BackendType.DOCLING,
            pdf_path=pdf_path
        )
        
        # Track doc for finally cleanup (prevents TOC memory leak)
        doc = None
        
        try:
            # Convert PDF with Docling (100% local models, offline mode)
            logger.info(f" Extracting {pdf_path} with Docling (LOCAL models, OFFLINE mode)...")
            try:
                doc_result = DoclingHelper.convert_pdf(pdf_path)
                logger.info(f" PDF conversion successful - using local models only")
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
            
            # Track failed tables for monitoring (count warnings from table failures)
            failed_count = len([w for w in result.warnings if 'extraction failed' in w])
            if failed_count > 0:
                result.metadata['failed_tables_count'] = failed_count
                logger.warning(f"{failed_count}/{len(tables)} tables failed to extract")
            
            # Extract metadata
            result.metadata = {**self._extract_metadata(pdf_path, doc), **result.metadata}
            
            # Note: quality_score is computed by QualityAssessor in strategy.py
            # Not setting it here to avoid confusion with actual computed score
            
        except Exception as e:
            logger.error(f"Docling extraction failed: {e}")
            result.error = str(e)
        finally:
            # ALWAYS clear TOC cache for this document to prevent memory leak
            # This runs whether extraction succeeded or failed
            if doc is not None:
                DoclingHelper.clear_toc_cache(id(doc))
        
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
        
        # === POST-PROCESS: Clean duplicate row headers from colspan handling ===
        # Docling's export_to_markdown duplicates cell content when a row header
        # has colspan attribute. Uses module-level clean_row_header_duplicates function.
        raw_table_text = clean_row_header_duplicates(raw_table_text)
        
        # === POST-PROCESS: Detect and add missing spanning headers ===
        # If the table's first row doesn't look like a spanning header (date/period),
        # check if there's a preceding TEXT item that should be the spanning header.
        if not _table_has_spanning_header(raw_table_text):
            # Try to find a preceding TEXT item that's the missing header
            preceding_header = DoclingHelper.find_preceding_spanning_header(
                doc, table_item, page_no
            )
            if preceding_header:
                num_cols = _count_columns(raw_table_text)
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
