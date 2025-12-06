"""
Unstructured backend for PDF extraction.

Uses the unstructured library for document parsing.
Good for mixed content types and various document formats.
"""

import time
import logging
from pathlib import Path
from typing import Dict, Any, List

from src.infrastructure.extraction.base import ExtractionBackend, ExtractionResult, BackendType
from src.utils.extraction_utils import PDFMetadataExtractor

logger = logging.getLogger(__name__)


class UnstructuredBackend(ExtractionBackend):
    """
    Unstructured extraction backend.
    
    Features:
    - Multi-format support (PDF, DOCX, HTML, etc.)
    - Layout detection
    - Table extraction
    - OCR support for scanned documents
    """
    
    def __init__(self, strategy: str = "auto"):
        """
        Initialize Unstructured backend.
        
        Args:
            strategy: Parsing strategy ("auto", "fast", "hi_res", "ocr_only")
        """
        self.strategy = strategy
    
    def extract(self, pdf_path: str, **kwargs) -> ExtractionResult:
        """
        Extract tables from PDF using Unstructured.
        
        Args:
            pdf_path: Path to PDF file
            **kwargs: Additional options
            
        Returns:
            ExtractionResult with tables and metadata
        """
        start_time = time.time()
        result = ExtractionResult(
            backend=BackendType.UNSTRUCTURED,
            pdf_path=pdf_path
        )
        
        try:
            from unstructured.partition.pdf import partition_pdf
            from unstructured.documents.elements import Table
            
            logger.info(f"Extracting {pdf_path} with Unstructured ({self.strategy})...")
            
            # Partition PDF
            elements = partition_pdf(
                filename=pdf_path,
                strategy=self.strategy,
                infer_table_structure=True,
            )
            
            # Count pages
            pages_seen = set()
            for el in elements:
                if hasattr(el, 'metadata') and hasattr(el.metadata, 'page_number'):
                    pages_seen.add(el.metadata.page_number)
            result.page_count = len(pages_seen) if pages_seen else 1
            
            # Extract tables
            tables = []
            table_index = 0
            for el in elements:
                if isinstance(el, Table):
                    table_data = self._process_table(el, pdf_path, table_index)
                    if table_data:
                        tables.append(table_data)
                        table_index += 1
            
            result.tables = tables
            result.metadata = self._extract_metadata(pdf_path)
            result.quality_score = 70.0  # Base score for Unstructured
            
            logger.info(f"Found {len(tables)} tables")
            
        except ImportError:
            result.error = "unstructured not installed. Run: pip install unstructured[pdf]"
            logger.error("Unstructured not available")
        except Exception as e:
            logger.error(f"Unstructured extraction failed: {e}")
            result.error = str(e)
        
        result.extraction_time = time.time() - start_time
        return result
    
    def _process_table(self, table_element, pdf_path: str, table_index: int) -> Dict[str, Any]:
        """Process a single table element."""
        try:
            # Get table content
            content = str(table_element)
            
            # Get page number
            page_no = 1
            if hasattr(table_element, 'metadata') and hasattr(table_element.metadata, 'page_number'):
                page_no = table_element.metadata.page_number or 1
            
            # Try to get HTML/structured content
            html_content = None
            if hasattr(table_element, 'metadata') and hasattr(table_element.metadata, 'text_as_html'):
                html_content = table_element.metadata.text_as_html
            
            # Convert to markdown if possible
            if html_content:
                markdown = self._html_to_markdown(html_content)
            else:
                markdown = content
            
            return {
                'content': markdown,
                'metadata': {
                    'source_doc': Path(pdf_path).name,
                    'page_no': page_no,
                    'table_title': f"Table {table_index + 1} on page {page_no}",
                    'year': PDFMetadataExtractor.extract_year(Path(pdf_path).name),
                    'quarter': PDFMetadataExtractor.extract_quarter(Path(pdf_path).name),
                    'report_type': PDFMetadataExtractor.extract_report_type(Path(pdf_path).name),
                },
                'html_content': html_content,
            }
        except Exception as e:
            logger.error(f"Error processing table: {e}")
            return None
    
    def _html_to_markdown(self, html: str) -> str:
        """Convert HTML table to markdown format."""
        try:
            from bs4 import BeautifulSoup
            
            soup = BeautifulSoup(html, 'html.parser')
            table = soup.find('table')
            
            if not table:
                return html
            
            rows = table.find_all('tr')
            if not rows:
                return html
            
            lines = []
            for i, row in enumerate(rows):
                cells = row.find_all(['th', 'td'])
                cell_texts = [cell.get_text(strip=True) for cell in cells]
                lines.append("| " + " | ".join(cell_texts) + " |")
                
                # Add separator after header
                if i == 0:
                    lines.append("|" + "|".join(["---" for _ in cells]) + "|")
            
            return "\n".join(lines)
        except Exception:
            return html
    
    def _extract_metadata(self, pdf_path: str) -> Dict[str, Any]:
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
        return "Unstructured"
    
    def get_backend_type(self) -> BackendType:
        """Get backend type."""
        return BackendType.UNSTRUCTURED
    
    def is_available(self) -> bool:
        """Check if Unstructured is available."""
        try:
            from unstructured.partition.pdf import partition_pdf
            return True
        except ImportError:
            return False
    
    def get_priority(self) -> int:
        """Get priority (4 = lower priority)."""
        return 4
    
    def get_version(self) -> str:
        """Get Unstructured version."""
        try:
            import unstructured
            return unstructured.__version__
        except (ImportError, AttributeError) as e:
            logger.debug(f"Could not get Unstructured version: {e}")
            return "unknown"
    
    def supports_feature(self, feature: str) -> bool:
        """Check feature support."""
        supported = {
            'multi_format', 'layout_detection', 'ocr', 
            'table_extraction', 'mixed_content'
        }
        return feature in supported
