"""
pdfplumber backend for PDF extraction.

Uses existing pdfplumber code from scrapers/pdf_scraper.py.
Good for scanned PDFs and complex layouts.
"""

import time
import logging
from pathlib import Path
from typing import Dict, Any, List

from src.extraction.base import ExtractionBackend, ExtractionResult, BackendType
from src.utils.extraction_utils import PDFMetadataExtractor

logger = logging.getLogger(__name__)


class PDFPlumberBackend(ExtractionBackend):
    """
    pdfplumber extraction backend.
    
    Features:
    - Good for scanned PDFs
    - Handles 2-column layouts
    - HTML extraction for complex tables
    - Block-based title extraction
    """
    
    def __init__(self):
        """Initialize pdfplumber backend."""
        pass
    
    def extract(self, pdf_path: str, **kwargs) -> ExtractionResult:
        """
        Extract tables from PDF using pdfplumber.
        
        Args:
            pdf_path: Path to PDF file
            **kwargs: Additional options
            
        Returns:
            ExtractionResult with tables and metadata
        """
        start_time = time.time()
        result = ExtractionResult(
            backend=BackendType.PDFPLUMBER,
            pdf_path=pdf_path
        )
        
        try:
            import pdfplumber
            
            logger.info(f"Extracting {pdf_path} with pdfplumber...")
            
            tables = []
            with pdfplumber.open(pdf_path) as pdf:
                result.page_count = len(pdf.pages)
                
                for page in pdf.pages:
                    page_tables = self._extract_tables_from_page(page)
                    tables.extend(page_tables)
            
            result.tables = tables
            result.metadata = self._extract_metadata(pdf_path)
            result.quality_score = 65.0  # Base score for pdfplumber
            
            logger.info(f"Found {len(tables)} tables")
            
        except ImportError:
            result.error = "pdfplumber not installed"
            logger.error("pdfplumber not available")
        except Exception as e:
            logger.error(f"pdfplumber extraction failed: {e}")
            result.error = str(e)
        
        result.extraction_time = time.time() - start_time
        return result
    
    def _extract_tables_from_page(self, page) -> List[Dict[str, Any]]:
        """Extract tables from a single page."""
        tables = []
        
        settings = {
            "vertical_strategy": "text",
            "horizontal_strategy": "lines",
            "intersection_y_tolerance": 10,
            "text_x_tolerance": 5,
        }
        
        page_tables = page.find_tables(settings)
        
        for i, table in enumerate(page_tables):
            try:
                data = table.extract()
                if not data or len(data) < 2:
                    continue
                
                # Convert to markdown-like format
                markdown = self._to_markdown(data)
                
                tables.append({
                    'content': markdown,
                    'metadata': {
                        'page_no': page.page_number,
                        'table_title': f"Table {i+1} on page {page.page_number}"
                    }
                })
                
            except Exception as e:
                logger.error(f"Error extracting table {i}: {e}")
                continue
        
        return tables
    
    def _to_markdown(self, data: List[List]) -> str:
        """Convert table data to markdown format."""
        if not data:
            return ""
        
        lines = []
        
        # Header
        header = data[0]
        lines.append("| " + " | ".join(str(cell) if cell else "" for cell in header) + " |")
        
        # Separator
        lines.append("|" + "|".join(["---" for _ in header]) + "|")
        
        # Data rows
        for row in data[1:]:
            lines.append("| " + " | ".join(str(cell) if cell else "" for cell in row) + " |")
        
        return "\n".join(lines)
    
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
        return "pdfplumber"
    
    def get_backend_type(self) -> BackendType:
        """Get backend type."""
        return BackendType.PDFPLUMBER
    
    def is_available(self) -> bool:
        """Check if pdfplumber is available."""
        try:
            import pdfplumber
            return True
        except ImportError:
            return False
    
    def get_priority(self) -> int:
        """Get priority (3 = third choice)."""
        return 3
    
    def get_version(self) -> str:
        """Get pdfplumber version."""
        try:
            import pdfplumber
            return pdfplumber.__version__
        except (ImportError, AttributeError) as e:
            logger.debug(f"Could not get pdfplumber version: {e}")
            return "unknown"
    
    def supports_feature(self, feature: str) -> bool:
        """Check feature support."""
        supported = {'scanned_pdfs', 'complex_layouts', '2_column_layouts'}
        return feature in supported
