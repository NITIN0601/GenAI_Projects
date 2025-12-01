"""
Camelot backend for PDF extraction.

Camelot is excellent for extracting tables from PDFs with lattice (grid lines)
or stream (whitespace-separated) detection strategies.
"""

import time
import logging
from pathlib import Path
from typing import Dict, Any, List

from src.extraction.base import ExtractionBackend, ExtractionResult, BackendType
from src.utils.extraction_utils import PDFMetadataExtractor

logger = logging.getLogger(__name__)


class CamelotBackend(ExtractionBackend):
    """
    Camelot extraction backend.
    
    Features:
    - Lattice detection (tables with grid lines)
    - Stream detection (whitespace-separated)
    - High accuracy for structured tables
    - Good for financial reports
    """
    
    def __init__(self, flavor: str = "lattice"):
        """
        Initialize Camelot backend.
        
        Args:
            flavor: Detection strategy ('lattice' or 'stream')
        """
        self.flavor = flavor
    
    def extract(self, pdf_path: str, **kwargs) -> ExtractionResult:
        """
        Extract tables from PDF using Camelot.
        
        Args:
            pdf_path: Path to PDF file
            **kwargs: Additional options (pages, flavor, etc.)
            
        Returns:
            ExtractionResult with tables and metadata
        """
        start_time = time.time()
        result = ExtractionResult(
            backend=BackendType.CAMELOT,
            pdf_path=pdf_path
        )
        
        try:
            import camelot
            
            flavor = kwargs.get('flavor', self.flavor)
            pages = kwargs.get('pages', 'all')
            
            logger.info(f"Extracting {pdf_path} with Camelot (flavor={flavor})...")
            
            # Extract tables
            tables_obj = camelot.read_pdf(
                pdf_path,
                pages=pages,
                flavor=flavor
            )
            
            result.page_count = len(set(t.page for t in tables_obj))
            
            # Convert to our format
            tables = []
            for i, table in enumerate(tables_obj):
                try:
                    # Get table data
                    df = table.df
                    
                    if df.empty or len(df) < 2:
                        continue
                    
                    # Convert to markdown
                    markdown = self._to_markdown(df.values.tolist())
                    
                    tables.append({
                        'content': markdown,
                        'metadata': {
                            'page_no': table.page,
                            'table_title': f"Table {i+1} on page {table.page}",
                            'accuracy': table.accuracy,
                            'whitespace': table.whitespace
                        }
                    })
                    
                except Exception as e:
                    logger.error(f"Error processing table {i}: {e}")
                    continue
            
            result.tables = tables
            result.metadata = self._extract_metadata(pdf_path)
            
            # Quality score based on average accuracy
            if tables:
                avg_accuracy = sum(
                    t['metadata'].get('accuracy', 0) 
                    for t in tables
                ) / len(tables)
                result.quality_score = avg_accuracy
            else:
                result.quality_score = 0.0
            
            logger.info(f"Found {len(tables)} tables with avg accuracy {result.quality_score:.1f}")
            
        except ImportError:
            result.error = "Camelot not installed (pip install camelot-py[cv])"
            logger.error("Camelot not available")
        except Exception as e:
            logger.error(f"Camelot extraction failed: {e}")
            result.error = str(e)
        
        result.extraction_time = time.time() - start_time
        return result
    
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
        return "Camelot"
    
    def get_backend_type(self) -> BackendType:
        """Get backend type."""
        return BackendType.CAMELOT
    
    def is_available(self) -> bool:
        """Check if Camelot is available."""
        try:
            import camelot
            return True
        except ImportError:
            return False
    
    def get_priority(self) -> int:
        """Get priority (4 = fourth choice)."""
        return 4
    
    def get_version(self) -> str:
        """Get Camelot version."""
        try:
            import camelot
            return camelot.__version__
        except (ImportError, AttributeError) as e:
            logger.debug(f"Could not get Camelot version: {e}")
            return "unknown"
    
    def supports_feature(self, feature: str) -> bool:
        """Check feature support."""
        supported = {
            'lattice_detection', 'stream_detection', 
            'accuracy_score', 'structured_tables'
        }
        return feature in supported
