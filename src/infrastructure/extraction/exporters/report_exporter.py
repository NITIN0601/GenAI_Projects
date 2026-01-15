"""
Report exporter for extraction results.

Exports extraction results to CSV and Excel report formats.
Extracted from extractor.py for better modularity.
"""

import csv
import re
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

from src.utils import get_logger

logger = get_logger(__name__)


class ReportExporter:
    """
    Export extraction results to CSV and Excel reports.
    
    Handles:
    - CSV report generation with table metadata
    - Excel report with pandas (if available)
    - Row header formatting with hierarchy
    """
    
    def __init__(self, output_dir: Optional[str] = None, output_format: str = 'both'):
        """
        Initialize report exporter.
        
        Args:
            output_dir: Directory for output files (default: from settings)
            output_format: Output format - 'csv', 'excel', or 'both'
        """
        self.output_format = output_format
        
        if output_dir:
            self.output_dir = Path(output_dir)
        else:
            try:
                from config.settings import settings
                self.output_dir = Path(settings.EXTRACTION_REPORT_DIR)
            except (ImportError, AttributeError):
                self.output_dir = Path("data/reports")
        
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def save_report(self, result) -> Optional[str]:
        """
        Save a detailed report of extracted tables.
        
        Args:
            result: ExtractionResult object
            
        Returns:
            Path to the created report file, or None on failure
        """
        if not result.is_successful() or not result.tables:
            return None
        
        try:
            # Prepare report data
            rows = self._prepare_report_rows(result)
            
            if not rows:
                return None
            
            # Generate filename base
            source_name = Path(result.pdf_path).stem
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            base_path = self.output_dir / f"table_report_{source_name}_{timestamp}"
            
            saved_paths = []
            
            # Save CSV
            if self.output_format in ('csv', 'both'):
                csv_path = self._save_csv(rows, base_path)
                if csv_path:
                    saved_paths.append(csv_path)
            
            # Save Excel
            if self.output_format in ('excel', 'both'):
                excel_path = self._save_excel(rows, base_path)
                if excel_path:
                    saved_paths.append(excel_path)
            
            return saved_paths[0] if saved_paths else None
            
        except Exception as e:
            logger.error(f"Failed to save table report: {e}")
            return None
    
    def _prepare_report_rows(self, result) -> List[Dict[str, Any]]:
        """
        Prepare rows for the report from extraction result.
        
        Args:
            result: ExtractionResult object
            
        Returns:
            List of row dictionaries
        """
        from src.infrastructure.extraction.formatters.table_formatter import TableStructureFormatter
        
        rows = []
        for table in result.tables:
            meta = table.get('metadata', {})
            content = table.get('content', '')
            
            # Use TableStructureFormatter for proper extraction
            parsed = TableStructureFormatter.parse_markdown_table(content)
            
            # Get structured row headers
            row_headers_structured = parsed.get('row_headers_structured', [])
            
            # Format row headers with hierarchy indication
            formatted_headers = self._format_row_headers(row_headers_structured)
            row_headers_str = '; '.join(formatted_headers)
            if len(row_headers_structured) > 15:
                row_headers_str += f"... (+{len(row_headers_structured)-15} more)"
            
            # Get subsections
            subsections = parsed.get('subsections', [])
            subsections_str = '; '.join(subsections[:5]) if subsections else ''
            if len(subsections) > 5:
                subsections_str += f"... (+{len(subsections)-5} more)"
            
            # Clean table title
            table_title = self._clean_title(
                meta.get('original_table_title') or meta.get('table_title', 'N/A')
            )
            
            rows.append({
                'Page No': meta.get('page_no', 'N/A'),
                'Table Title': table_title.strip(),
                'Row Headers': row_headers_str,
                'Subsections': subsections_str,
                'Source': meta.get('source_doc', 'N/A'),
                'Quality Score': meta.get('quality_score', result.quality_score),
                'Backend': result.backend.value if result.backend else 'N/A'
            })
        
        return rows
    
    def _format_row_headers(self, row_headers_structured: List[Dict], limit: int = 15) -> List[str]:
        """
        Format row headers with hierarchy indication.
        
        Args:
            row_headers_structured: List of structured row header dicts
            limit: Maximum number of headers to include
            
        Returns:
            List of formatted header strings
        """
        formatted = []
        for rh in row_headers_structured[:limit]:
            text = rh.get('text', '')
            if not text:
                continue
            indent = '  ' * rh.get('indent_level', 0)
            if rh.get('is_subsection'):
                formatted.append(f"[{text}]")
            elif rh.get('is_total'):
                formatted.append(f"**{text}**")
            else:
                formatted.append(f"{indent}{text}")
        return formatted
    
    def _clean_title(self, title: str) -> str:
        """
        Clean table title - remove section numbers and row ranges.
        
        Args:
            title: Raw table title
            
        Returns:
            Cleaned title string
        """
        if not title:
            return 'N/A'
        
        # Remove leading section numbers like "17." or "17 "
        title = re.sub(r'^\d+[\.\:\s]+\s*', '', title)
        # Remove Note/Table prefixes
        title = re.sub(r'^Note\s+\d+\.?\s*[-–:]?\s*', '', title, flags=re.IGNORECASE)
        title = re.sub(r'^Table\s+\d+\.?\s*[-–:]?\s*', '', title, flags=re.IGNORECASE)
        # Remove row range patterns
        title = re.sub(r'\s*\(Rows?\s*\d+[-–]\d+\)\s*$', '', title, flags=re.IGNORECASE)
        
        return title.strip()
    
    def _save_csv(self, rows: List[Dict], base_path: Path) -> Optional[str]:
        """Save report to CSV file."""
        try:
            csv_path = f"{base_path}.csv"
            with open(csv_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=rows[0].keys())
                writer.writeheader()
                writer.writerows(rows)
            logger.info(f"Saved extraction report to {csv_path}")
            return csv_path
        except Exception as e:
            logger.error(f"Failed to save CSV report: {e}")
            return None
    
    def _save_excel(self, rows: List[Dict], base_path: Path) -> Optional[str]:
        """Save report to Excel file."""
        try:
            import pandas as pd
            xlsx_path = f"{base_path}.xlsx"
            df = pd.DataFrame(rows)
            df.to_excel(xlsx_path, index=False, sheet_name='Extraction Report')
            logger.info(f"Saved extraction report to {xlsx_path}")
            return xlsx_path
        except ImportError:
            logger.warning("pandas not available, skipping Excel export")
            return None
        except Exception as e:
            logger.error(f"Failed to save Excel report: {e}")
            return None


# Singleton instance
_exporter_instance = None


def get_report_exporter(output_dir: Optional[str] = None) -> ReportExporter:
    """Get or create ReportExporter singleton instance."""
    global _exporter_instance
    if _exporter_instance is None:
        _exporter_instance = ReportExporter(output_dir=output_dir)
    return _exporter_instance
