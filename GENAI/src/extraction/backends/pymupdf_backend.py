"""
PyMuPDF backend for PDF extraction.

Uses PyMuPDF's native table detection - fast and accurate.
Based on existing code from unwanted/pymupdf_scraper.py.
"""

import time
import logging
from pathlib import Path
from typing import Dict, Any, List

from src.extraction.base import ExtractionBackend, ExtractionResult, BackendType
from src.utils.extraction_utils import PDFMetadataExtractor

logger = logging.getLogger(__name__)


class PyMuPDFBackend(ExtractionBackend):
    """
    PyMuPDF (fitz) extraction backend.
    
    Features:
    - Fast extraction (10-100x faster than pdfplumber)
    - Native table detection
    - Good for complex multi-column layouts
    - Accurate for financial documents
    """
    
    def __init__(self):
        """Initialize PyMuPDF backend."""
        pass
    
    def extract(self, pdf_path: str, **kwargs) -> ExtractionResult:
        """
        Extract tables from PDF using PyMuPDF.
        
        Args:
            pdf_path: Path to PDF file
            **kwargs: Additional options
            
        Returns:
            ExtractionResult with tables and metadata
        """
        start_time = time.time()
        result = ExtractionResult(
            backend=BackendType.PYMUPDF,
            pdf_path=pdf_path
        )
        
        try:
            import fitz  # PyMuPDF
            
            logger.info(f"Extracting {pdf_path} with PyMuPDF...")
            
            # Open PDF
            doc = fitz.open(pdf_path)
            result.page_count = len(doc)
            
            # Extract tables from each page
            tables = []
            for page_num in range(len(doc)):
                page = doc[page_num]
                page_tables = self._extract_tables_from_page(page, page_num + 1)
                tables.extend(page_tables)
            
            doc.close()
            
            result.tables = tables
            result.metadata = self._extract_metadata(pdf_path)
            result.quality_score = 70.0  # Base score for PyMuPDF
            
            logger.info(f"Found {len(tables)} tables")
            
        except ImportError:
            result.error = "PyMuPDF not installed"
            logger.error("PyMuPDF (fitz) not available")
        except Exception as e:
            logger.error(f"PyMuPDF extraction failed: {e}")
            result.error = str(e)
        
        result.extraction_time = time.time() - start_time
        return result
    
    def _extract_tables_from_page(self, page, page_num: int) -> List[Dict[str, Any]]:
        """Extract tables from a single page using PyMuPDF's find_tables()."""
        tables = []
        
        # Find tables using PyMuPDF's native table detection
        page_tables = page.find_tables()
        
        if not page_tables or not page_tables.tables:
            return tables
        
        for i, table in enumerate(page_tables.tables):
            try:
                # Extract table data
                table_data = table.extract()
                
                if not table_data or len(table_data) < 2:
                    continue
                
                # Convert to markdown
                markdown = self._to_markdown(table_data)
                
                # Extract title (look above table)
                title = self._extract_title(page, table.bbox, page_num)
                if not title:
                    title = f"Table {i+1} on page {page_num}"
                
                tables.append({
                    'content': markdown,
                    'metadata': {
                        'page_no': page_num,
                        'table_title': title
                    }
                })
                
            except Exception as e:
                logger.error(f"Error extracting table {i} on page {page_num}: {e}")
                continue
        
        return tables
    
    def _extract_title(self, page, bbox: tuple, page_num: int) -> str:
        """Extract table title from text above the table."""
        import fitz
        import re
        
        x0, y0, x1, y1 = bbox
        
        # Define search area above the table
        search_rect = fitz.Rect(
            x0,
            max(0, y0 - 60),  # Look 60 points above
            x1,
            y0
        )
        
        # Extract text from search area
        text_above = page.get_text("text", clip=search_rect)
        
        if not text_above:
            return ""
        
        # Process lines
        lines = [l.strip() for l in text_above.split('\n') if l.strip()]
        
        # Filter and find best title candidate
        for line in reversed(lines):  # Start from closest to table
            # Skip noise
            if any(noise in line.lower() for noise in [
                'table of contents', 'notes to', 'unaudited',
                'dollars in millions', 'page ', 'form 10-'
            ]):
                continue
            
            # Skip lines that are just numbers or too short
            if len(line) < 10 or line.replace(',', '').replace('.', '').replace('$', '').replace(' ', '').isdigit():
                continue
            
            # Skip lines with mostly dollar signs
            if line.count('$') > 3:
                continue
            
            # This looks like a good title
            if len(line) < 200:  # Not too long
                # Clean up superscripts and special characters
                clean_title = re.sub(r'[¹²³⁴⁵⁶⁷⁸⁹⁰]', '', line)
                return clean_title.strip()
        
        return ""
    
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
        return "PyMuPDF"
    
    def get_backend_type(self) -> BackendType:
        """Get backend type."""
        return BackendType.PYMUPDF
    
    def is_available(self) -> bool:
        """Check if PyMuPDF is available."""
        try:
            import fitz
            return True
        except ImportError:
            return False
    
    def get_priority(self) -> int:
        """Get priority (2 = second choice)."""
        return 2
    
    def get_version(self) -> str:
        """Get PyMuPDF version."""
        try:
            import fitz
            return fitz.version[0]
        except (ImportError, AttributeError, IndexError) as e:
            logger.debug(f"Could not get PyMuPDF version: {e}")
            return "unknown"
    
    def supports_feature(self, feature: str) -> bool:
        """Check feature support."""
        supported = {'fast_extraction', 'text_extraction', 'native_table_detection'}
        return feature in supported
