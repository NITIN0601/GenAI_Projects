"""
Unified PDF extraction system with multiple backends and automatic fallback.

Main extractor class that orchestrates multiple backends with fallback strategy.
"""

import os
from pathlib import Path
from typing import Optional, List, Dict, Any

from src.infrastructure.extraction.base import ExtractionBackend, ExtractionResult, BackendType, ExtractionError
from src.infrastructure.extraction.strategy import ExtractionStrategy
from src.infrastructure.extraction.quality import QualityAssessor
from src.infrastructure.extraction.cache import ExtractionCache
from src.infrastructure.extraction.backends import (
    DoclingBackend,
    PyMuPDFBackend,
    PDFPlumberBackend,
    CamelotBackend
)
from src.utils import get_logger
from src.utils.metrics import get_metrics_collector
from config.settings import settings


logger = get_logger(__name__)
metrics = get_metrics_collector()


class UnifiedExtractor:
    """
    Unified PDF extraction with multiple backends.
    
    Features:
    - Multiple extraction backends (Docling, PyMuPDF, etc.)
    - Automatic quality assessment
    - Intelligent fallback mechanism
    - Result caching
    - Configurable behavior
    
    Example:
        >>> extractor = UnifiedExtractor()
        >>> result = extractor.extract("document.pdf")
        >>> print(f"Backend: {result.backend.value}")
        >>> print(f"Quality: {result.quality_score:.1f}")
        >>> print(f"Tables: {len(result.tables)}")
    """
    
    def __init__(
        self,
        backends: Optional[List[str]] = None,
        min_quality: float = 60.0,
        enable_caching: bool = True,
        cache_ttl_hours: int = 168
    ):
        """
        Initialize unified extractor.
        
        Args:
            backends: List of backend names (default: from settings)
            min_quality: Minimum quality score threshold
            enable_caching: Enable result caching
            cache_ttl_hours: Cache time-to-live in hours
        """
        # Use config if not specified
        if backends is None:
            try:
                from config.settings import settings
                backends = getattr(settings, 'EXTRACTION_BACKENDS', ['docling'])
            except ImportError:
                logger.warning("config.settings not found, using default backends: ['docling']")
                backends = ['docling']  # Fallback default
            except Exception as e:
                logger.error(f"Error loading backends from settings: {e}, using default backends: ['docling']")
                backends = ['docling'] # Fallback default
        
        self.min_quality = min_quality
        self.enable_caching = enable_caching
        
        # Initialize backends
        self.backends = self._load_backends(backends)
        
        # Initialize strategy
        self.quality_assessor = QualityAssessor()
        self.strategy = ExtractionStrategy(
            backends=self.backends,
            quality_assessor=self.quality_assessor
        )
        
        # Initialize cache
        self.cache = ExtractionCache(
            ttl_hours=cache_ttl_hours,
            enabled=enable_caching
        ) if enable_caching else None
        
        logger.info(
            f"UnifiedExtractor initialized: "
            f"backends={[b.get_name() for b in self.backends]}, "
            f"min_quality={min_quality}, "
            f"caching={enable_caching}"
        )
    
    def extract(
        self,
        pdf_path: str,
        force: bool = False,
        **kwargs
    ) -> ExtractionResult:
        """
        Extract tables from PDF with automatic fallback.
        
        Args:
            pdf_path: Path to PDF file
            force: Force re-extraction (ignore cache)
            **kwargs: Additional extraction options
            
        Returns:
            Extraction result with best quality
            
        Raises:
            FileNotFoundError: If PDF file doesn't exist
            ValueError: If file is not a PDF or too large
        """
        # Input validation
        pdf_file = Path(pdf_path)
        
        # Check file exists
        if not pdf_file.exists():
            error_msg = f"PDF file not found: {pdf_path}"
            logger.error(error_msg)
            raise FileNotFoundError(error_msg)
        
        # Check file extension
        if not pdf_file.suffix.lower() == '.pdf':
            error_msg = f"Not a PDF file: {pdf_path} (extension: {pdf_file.suffix})"
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        # Check file size (prevent DoS with huge files)
        max_size_mb = kwargs.get('max_size_mb', 500)  # Default 500MB limit
        file_size_mb = pdf_file.stat().st_size / (1024 * 1024)
        if file_size_mb > max_size_mb:
            error_msg = f"PDF too large: {file_size_mb:.1f}MB > {max_size_mb}MB"
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        # Resolve to absolute path
        pdf_path = str(pdf_file.resolve())
        
        logger.info(f"Starting extraction: {pdf_file.name} ({file_size_mb:.1f}MB)")
        
        # Check cache
        if self.cache and not force:
            cached = self.cache.get(pdf_path)
            if cached:
                logger.info(f"Using cached result for {pdf_path}")
                # Record cache hit
                metrics.record_extraction(
                    pdf_path=pdf_path,
                    backend=cached.backend.value,
                    success=True,
                    tables_found=len(cached.tables),
                    quality_score=cached.quality_score,
                extraction_time=0.0  # Cache hit
                )
                self._save_table_report(cached)
                return cached
        
        # Extract with fallback
        logger.info(f"Extracting {pdf_path}...")
        result = self.strategy.extract_with_fallback(
            pdf_path,
            min_quality=self.min_quality
        )
        
        # Record metrics
        metrics.record_extraction(
            pdf_path=pdf_path,
            backend=result.backend.value,
            success=result.is_successful(),
            tables_found=len(result.tables),
            quality_score=result.quality_score,
            extraction_time=result.extraction_time,
            error=result.error
        )
        
        # Cache result
        if self.cache and result.is_successful():
            self.cache.set(pdf_path, result)
            logger.info(f"Cached extraction result for {pdf_path}")
            
        # Save table report
        self._save_table_report(result)

        
        logger.info(
            f"Extraction complete: {len(result.tables)} tables, "
            f"quality={result.quality_score:.1f}, time={result.extraction_time:.2f}s"
        )
        
        return result
    
    def extract_batch(
        self,
        pdf_paths: List[str],
        force: bool = False
    ) -> List[ExtractionResult]:
        """
        Extract multiple PDFs.
        
        Args:
            pdf_paths: List of PDF paths
            force: Force re-extraction
            
        Returns:
            List of extraction results
        """
        results = []
        
        for pdf_path in pdf_paths:
            try:
                result = self.extract(pdf_path, force=force)
                results.append(result)
            except Exception as e:
                logger.error(f"Failed to extract {pdf_path}: {e}")
                # Create error result
                error_result = ExtractionResult(
                    pdf_path=pdf_path,
                    error=str(e)
                )
                results.append(error_result)
        
        return results

    def _save_table_report(self, result: ExtractionResult):
        """
        Save a detailed report of extracted tables to CSV and/or Excel.
        
        Args:
            result: Extraction result
        """
        if not result.is_successful() or not result.tables:
            return
            
        try:
            import csv
            from datetime import datetime
            
            # Get output settings
            output_dir = Path(settings.EXTRACTION_REPORT_DIR)
            output_format = getattr(settings, 'EXTRACTION_REPORT_FORMAT', 'both')
            
            output_dir.mkdir(parents=True, exist_ok=True)
            
            # Generate filename base
            source_name = Path(result.pdf_path).stem
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            base_path = output_dir / f"table_report_{source_name}_{timestamp}"
            
            # Prepare report data
            rows = []
            for table in result.tables:
                meta = table.get('metadata', {})
                content = table.get('content', '')
                
                # Use TableStructureFormatter for proper extraction
                from src.infrastructure.extraction.formatters.table_formatter import TableStructureFormatter
                parsed = TableStructureFormatter.parse_markdown_table(content)
                
                # Get structured row headers
                row_headers_structured = parsed.get('row_headers_structured', [])
                
                # Format row headers with hierarchy indication
                formatted_headers = []
                for rh in row_headers_structured[:15]:  # Limit to first 15
                    text = rh.get('text', '')
                    if not text:
                        continue
                    indent = '  ' * rh.get('indent_level', 0)
                    if rh.get('is_subsection'):
                        formatted_headers.append(f"[{text}]")
                    elif rh.get('is_total'):
                        formatted_headers.append(f"**{text}**")
                    else:
                        formatted_headers.append(f"{indent}{text}")
                
                row_headers_str = '; '.join(formatted_headers)
                if len(row_headers_structured) > 15:
                    row_headers_str += f"... (+{len(row_headers_structured)-15} more)"
                
                # Get subsections
                subsections = parsed.get('subsections', [])
                subsections_str = '; '.join(subsections[:5]) if subsections else ''
                if len(subsections) > 5:
                    subsections_str += f"... (+{len(subsections)-5} more)"
                
                # Clean table title - remove section numbers and row ranges
                import re
                table_title = meta.get('original_table_title') or meta.get('table_title', 'N/A')
                # Remove leading section numbers like "17." or "17 "
                table_title = re.sub(r'^\d+[\.\:\s]+\s*', '', table_title)
                # Remove Note/Table prefixes
                table_title = re.sub(r'^Note\s+\d+\.?\s*[-–:]?\s*', '', table_title, flags=re.IGNORECASE)
                table_title = re.sub(r'^Table\s+\d+\.?\s*[-–:]?\s*', '', table_title, flags=re.IGNORECASE)
                # Remove row range patterns
                table_title = re.sub(r'\s*\(Rows?\s*\d+[-–]\d+\)\s*$', '', table_title, flags=re.IGNORECASE)
                
                rows.append({
                    'Page No': meta.get('page_no', 'N/A'),
                    'Table Title': table_title.strip(),
                    'Row Headers': row_headers_str,
                    'Subsections': subsections_str,
                    'Source': meta.get('source_doc', 'N/A'),
                    'Quality Score': meta.get('quality_score', result.quality_score),
                    'Backend': result.backend.value if result.backend else 'N/A'
                })
            
            # Save CSV
            if output_format in ('csv', 'both'):
                csv_path = f"{base_path}.csv"
                with open(csv_path, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.DictWriter(f, fieldnames=rows[0].keys())
                    writer.writeheader()
                    writer.writerows(rows)
                logger.info(f"Saved extraction report to {csv_path}")
            
            # Save Excel
            if output_format in ('excel', 'both'):
                try:
                    import pandas as pd
                    xlsx_path = f"{base_path}.xlsx"
                    df = pd.DataFrame(rows)
                    df.to_excel(xlsx_path, index=False, sheet_name='Extraction Report')
                    logger.info(f"Saved extraction report to {xlsx_path}")
                except ImportError:
                    logger.warning("pandas not available, skipping Excel export")
            
            # Save Excel with Index sheet (multi-sheet workbook)
            try:
                from src.infrastructure.extraction.formatters.excel_exporter import get_excel_exporter
                excel_exporter = get_excel_exporter()
                excel_path = excel_exporter.export_pdf_tables(
                    tables=result.tables,
                    source_pdf=result.pdf_path
                )
                if excel_path:
                    logger.info(f"Saved Excel with Index sheet to {excel_path}")
            except Exception as e:
                logger.warning(f"Failed to export Excel with Index sheet: {e}")
            
        except Exception as e:
            logger.error(f"Failed to save table report: {e}")
    
    def get_stats(self) -> dict:
        """
        Get extractor statistics.
        
        Returns:
            Dictionary with stats
        """
        stats = {
            'backends': self.strategy.get_backend_info(),
            'available_backends': self.strategy.get_available_backends(),
            'min_quality': self.min_quality,
        }
        
        if self.cache:
            stats['cache'] = self.cache.get_stats()
        
        return stats
    
    def clear_cache(self) -> int:
        """
        Clear extraction cache.
        
        Returns:
            Number of cache files deleted
        """
        if self.cache:
            return self.cache.clear()
        return 0
    
    def _load_backends(
        self,
        backend_names: Optional[List[str]]
    ) -> List[ExtractionBackend]:
        """Load and initialize backends."""
        # Backend initialization options
        options = {}
        
        # Available backends
        available = {
            'docling': DoclingBackend,
            'pymupdf': PyMuPDFBackend,
            'pdfplumber': PDFPlumberBackend,
            'camelot': CamelotBackend,
        }
        
        # Use specified backends or all available
        if backend_names:
            backend_names = [name.lower() for name in backend_names]
        else:
            backend_names = list(available.keys())
        
        # Initialize backends
        backends = []
        for name in backend_names:
            if name not in available:
                logger.warning(f"Unknown backend: {name}")
                continue
            
            try:
                backend_class = available[name]
                backend = backend_class(**options)
                
                if backend.is_available():
                    backends.append(backend)
                    logger.info(f"Loaded backend: {backend.get_name()}")
                else:
                    logger.warning(f"Backend {name} not available (missing dependencies)")
                    
            except Exception as e:
                logger.error(f"Failed to load backend {name}: {e}")
        
        if not backends:
            raise ValueError("No backends available")
        
        return backends


# Convenience function
def extract_pdf(
    pdf_path: str,
    min_quality: float = 60.0,
    enable_caching: bool = True
) -> ExtractionResult:
    """
    Quick extraction with default settings.
    
    Args:
        pdf_path: Path to PDF file
        min_quality: Minimum quality threshold
        enable_caching: Enable caching
        
    Returns:
        Extraction result
    """
    extractor = UnifiedExtractor(
        min_quality=min_quality,
        enable_caching=enable_caching
    )
    return extractor.extract(pdf_path)
