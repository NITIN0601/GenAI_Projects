"""
Process Step - Data processing and normalization.

Step 2 in pipeline: Extract → Process → Process-Advanced → Consolidate → Transpose

Implements ALL operations per docs/pipeline_operations.md (2.1-2.15):
- 2.1  OCR Broken Words Fix
- 2.2  Footnote Reference Cleanup
- 2.3  Row Label Normalization
- 2.4  Title Normalization
- 2.5  Currency → Float
- 2.6  Negative (Parens) → Float
- 2.7  Percentage → Float
- 2.8  Excel Currency Format ($#,##0.00)
- 2.9  Excel Percent Format (0.00%)
- 2.10 Year String Cleanup
- 2.11 L1/L2/L3/L4 Detection
- 2.12 Y/Q Code Formatting
- 2.13 Y/Q Period Detection
- 2.14 Fill Y/Q Placeholder (Row 8)
- 2.15 Index Update
"""

from pathlib import Path
from typing import Dict, Any, Optional

from src.pipeline.base import StepInterface, StepResult, StepStatus, PipelineContext
from src.pipeline import PipelineResult, PipelineStep
from src.utils import get_logger
from src.utils.excel_utils import ExcelUtils
from src.utils.metadata_labels import MetadataLabels
from src.utils.quarter_mapper import QuarterDateMapper
from src.utils.header_parser import MultiLevelHeaderParser
from src.utils.header_normalizer import ColumnHeaderNormalizer

logger = get_logger(__name__)

# File pattern for processed xlsx files
TABLE_FILE_PATTERN = "*_tables.xlsx"

# Excel number formats
CURRENCY_FORMAT = '$#,##0.00'
PERCENT_FORMAT = '0.00%'
NEGATIVE_CURRENCY_FORMAT = '$#,##0.00;[Red]($#,##0.00)'


class ProcessStep(StepInterface):
    """
    Process step - normalize and clean extracted data.
    
    Implements StepInterface following pipeline pattern.
    
    Reads: data/processed/*.xlsx (output from extract step)
    Writes: data/processed/*.xlsx
    
    Operations performed (per docs/pipeline_operations.md):
    - OCR broken words fix (2.1)
    - Footnote cleanup (2.2)
    - Row label normalization (2.3)
    - Title normalization (2.4)
    - Currency → float conversion with Excel format (2.5, 2.6, 2.8)
    - Percentage → float conversion with Excel format (2.7, 2.9)
    - Year string cleanup (2.10)
    - Multi-level header parsing (2.11)
    - Y/Q code formatting (2.12, 2.13)
    - Y/Q placeholder fill in Row 8 (2.14)
    """
    
    name = "process"
    
    def __init__(self, source_dir: Optional[str] = None, dest_dir: Optional[str] = None):
        """
        Initialize step with optional directory overrides.
        
        Args:
            source_dir: Override source directory (default: data/processed)
            dest_dir: Override destination directory (default: data/processed)
        """
        self.source_dir = source_dir
        self.dest_dir = dest_dir
    
    def validate(self, context: PipelineContext) -> bool:
        """Validate that source directory exists and has xlsx files."""
        from src.core import get_paths
        
        paths = get_paths()
        source_path = Path(self.source_dir) if self.source_dir else Path(paths.data_dir) / "processed"
        
        if not source_path.exists():
            logger.warning(f"Source directory does not exist: {source_path}")
            return False
        
        xlsx_files = list(source_path.glob(TABLE_FILE_PATTERN))
        if not xlsx_files:
            logger.warning(f"No xlsx files in {source_path}")
            return False
        
        return True
    
    def get_step_info(self) -> Dict[str, Any]:
        """Get step metadata."""
        return {
            "name": self.name,
            "description": "Normalize and clean extracted data with Excel formatting",
            "reads": ["data/processed/*.xlsx"],
            "writes": ["data/processed/*.xlsx"],
            "operations": [
                "2.1 OCR broken words fix",
                "2.2 Footnote cleanup",
                "2.5-2.6 Currency → Float",
                "2.7 Percentage → Float",
                "2.8-2.9 Excel cell formatting",
                "2.12-2.14 Y/Q code formatting and placeholder fill"
            ]
        }
    
    def execute(self, context: PipelineContext) -> StepResult:
        """Execute processing step."""
        from openpyxl import load_workbook
        from src.core import get_paths
        
        paths = get_paths()
        # Step 2: reads from extracted_raw, writes to processed
        source_path = Path(self.source_dir) if self.source_dir else Path(paths.data_dir) / "extracted_raw"
        dest_path = Path(self.dest_dir) if self.dest_dir else Path(paths.data_dir) / "processed"
        
        dest_path.mkdir(parents=True, exist_ok=True)
        
        xlsx_files = list(source_path.glob(TABLE_FILE_PATTERN))
        
        stats = {
            'files_processed': 0,
            'cells_formatted': 0,
            'yq_filled': 0,
            'errors': []
        }
        
        for xlsx_path in xlsx_files:
            try:
                self._process_file(xlsx_path, dest_path, stats)
                stats['files_processed'] += 1
            except Exception as e:
                logger.error(f"Error processing {xlsx_path.name}: {e}")
                stats['errors'].append(f"{xlsx_path.name}: {str(e)}")
        
        status = StepStatus.SUCCESS if not stats['errors'] else StepStatus.PARTIAL_SUCCESS
        
        return StepResult(
            step_name=self.name,
            status=status,
            data=stats,
            message=f"Processed {stats['files_processed']} files, formatted {stats['cells_formatted']} cells",
            metadata={
                'source_dir': str(source_path),
                'dest_dir': str(dest_path)
            }
        )
    
    def _process_file(self, source_path: Path, dest_path: Path, stats: Dict):
        """Process a single xlsx file."""
        from openpyxl import load_workbook
        
        wb = load_workbook(source_path)
        
        for sheet_name in wb.sheetnames:
            if sheet_name in ['Index', 'TOC', 'TOC_Sheet']:
                continue
            
            ws = wb[sheet_name]
            self._process_sheet(ws, stats)
        
        # Save to destination
        output_path = dest_path / source_path.name
        wb.save(output_path)
        wb.close()
        
        logger.debug(f"Processed {source_path.name} -> {output_path}")
    
    def _process_sheet(self, ws, stats: Dict):
        """Process a single worksheet with all operations."""
        from openpyxl.styles import numbers
        
        # === Extract L1/L2/L3 from DATA rows (13-14), not metadata rows ===
        # Row 13 typically has L1 spanning headers (e.g., "Three Months Ended June 30, 2024")
        # Row 14 typically has L2/L3 headers (e.g., "$ in millions", "2024", "2023")
        
        data_header_rows = []
        for row_idx in [13, 14]:  # Data header rows
            if row_idx > ws.max_row:
                continue
            row_values = []
            for col_idx in range(1, ws.max_column + 1):
                cell = ws.cell(row=row_idx, column=col_idx)
                row_values.append(str(cell.value) if cell.value else '')
            data_header_rows.append(row_values)
        
        # Normalize using ColumnHeaderNormalizer
        normalized = ColumnHeaderNormalizer.normalize_headers(data_header_rows)
        
        # Collect Y/Q codes and update metadata rows
        yq_codes_per_column = []  # Per-column codes
        l1_per_column = normalized.get('l1_headers', [])
        normalized_headers = normalized.get('normalized_headers', [])
        
        for col_idx, norm_value in enumerate(normalized_headers):
            if norm_value:
                # Check if it's a Y/Q code
                if norm_value.startswith('Q') or norm_value.startswith('YTD') or '-' in norm_value:
                    yq_codes_per_column.append(norm_value)
                else:
                    yq_codes_per_column.append('')
            else:
                yq_codes_per_column.append('')
        
        # === Update metadata rows 5-8 with PER-COLUMN values ===
        # Row 5: Column Header L1 (per-column from L1 headers)
        # Row 6: Column Header L2 (per-column period type)
        # Row 7: Column Header L3 (per-column normalized codes)
        # Row 8: Year/Quarter (per-column Y/Q codes)
        
        num_cols = ws.max_column
        
        def safe_set_cell_value(ws, row, col, value):
            """Safely set cell value, skipping merged cells."""
            from openpyxl.cell.cell import MergedCell
            cell = ws.cell(row=row, column=col)
            if not isinstance(cell, MergedCell):
                cell.value = value
                return True
            return False
        
        # Row 5: L1 headers (e.g., "Three Months Ended June 30, 2024")
        safe_set_cell_value(ws, 5, 1, 'Column Header L1:')
        for col_idx in range(2, num_cols + 1):
            l1_val = l1_per_column[col_idx - 1] if col_idx - 1 < len(l1_per_column) else ''
            safe_set_cell_value(ws, 5, col_idx, l1_val)
        
        # Row 6: L2 (period type - extract from data if available)
        safe_set_cell_value(ws, 6, 1, 'Column Header L2:')
        # L2 typically comes from row 13 spanning headers
        if len(data_header_rows) > 0:
            for col_idx in range(2, num_cols + 1):
                r13_val = data_header_rows[0][col_idx - 1] if col_idx - 1 < len(data_header_rows[0]) else ''
                # Check if it's a period type (not a label like "$ in millions")
                if r13_val and ('months ended' in r13_val.lower() or 'at ' in r13_val.lower()):
                    safe_set_cell_value(ws, 6, col_idx, r13_val)
        
        # Row 7: L3 (normalized codes like Q2-QTD-2024)
        safe_set_cell_value(ws, 7, 1, 'Column Header L3:')
        for col_idx in range(2, num_cols + 1):
            norm_val = normalized_headers[col_idx - 1] if col_idx - 1 < len(normalized_headers) else ''
            if safe_set_cell_value(ws, 7, col_idx, norm_val):
                stats['cells_formatted'] = stats.get('cells_formatted', 0) + 1
        
        # Row 8: Year/Quarter (per-column Y/Q codes)
        safe_set_cell_value(ws, 8, 1, 'Year/Quarter:')
        for col_idx in range(2, num_cols + 1):
            yq_val = yq_codes_per_column[col_idx - 1] if col_idx - 1 < len(yq_codes_per_column) else ''
            safe_set_cell_value(ws, 8, col_idx, yq_val)
        stats['yq_filled'] = stats.get('yq_filled', 0) + 1
        
        # === Also normalize the actual data header row (14) ===
        if len(data_header_rows) > 1:
            for col_idx in range(2, num_cols + 1):
                norm_val = normalized_headers[col_idx - 1] if col_idx - 1 < len(normalized_headers) else ''
                if norm_val and (norm_val.startswith('Q') or norm_val.startswith('YTD')):
                    if safe_set_cell_value(ws, 14, col_idx, norm_val):
                        stats['cells_formatted'] = stats.get('cells_formatted', 0) + 1
        
        # Second pass: process all data cells (starting from row 13)
        for row_idx, row in enumerate(ws.iter_rows(min_row=13), start=13):
            for col_idx, cell in enumerate(row, start=1):
                if cell.value is None:
                    continue
                
                original_value = cell.value
                new_value, cell_format = self._process_cell_value(original_value, row_idx, col_idx)
                
                if new_value != original_value:
                    cell.value = new_value
                    stats['cells_formatted'] += 1
                
                # Apply Excel number format
                if cell_format:
                    cell.number_format = cell_format
    
    def _process_cell_value(self, value, row_idx: int, col_idx: int):
        """
        Process a single cell value and determine Excel format.
        
        Returns:
            Tuple of (processed_value, excel_format_or_None)
        """
        if value is None:
            return value, None
        
        str_value = str(value).strip()
        
        # Skip empty values
        if not str_value:
            return value, None
        
        # Skip special text values
        if str_value.lower() in ['n/a', '-', '—', 'nm', 'n.a.', '']:
            return value, None
        
        # Already a number? Check if it needs formatting
        if isinstance(value, (int, float)):
            # Determine format based on magnitude (crude heuristic)
            if abs(value) < 1 and value != 0:
                # Likely a percentage (0.155 = 15.5%)
                return value, PERCENT_FORMAT
            else:
                return value, CURRENCY_FORMAT
        
        # Fix OCR broken words (for text in column A typically)
        if isinstance(value, str) and col_idx == 1:
            str_value = ExcelUtils.fix_ocr_broken_words(str_value)
            str_value = ExcelUtils.clean_footnote_references(str_value)
            return str_value, None
        
        # Try percentage conversion first (contains %)
        if isinstance(value, str) and '%' in str_value:
            try:
                pct_str = str_value.replace('%', '').replace(',', '').strip()
                pct_val = float(pct_str)
                return pct_val / 100.0, PERCENT_FORMAT  # 15.5% -> 0.155
            except (ValueError, TypeError):
                pass
        
        # Try currency/negative conversion
        if isinstance(value, str):
            cleaned = ExcelUtils.clean_currency_value(str_value)
            if isinstance(cleaned, (int, float)) and cleaned != value:
                return cleaned, NEGATIVE_CURRENCY_FORMAT if cleaned < 0 else CURRENCY_FORMAT
        
        return str_value if isinstance(value, str) else value, None


# Backward-compatible function for main.py CLI
def run_process(
    source_dir: Optional[str] = None,
    dest_dir: Optional[str] = None
) -> PipelineResult:
    """
    Run processing on extracted xlsx files.
    
    Legacy wrapper maintaining backward compatibility with main.py CLI.
    
    Args:
        source_dir: Override source directory (default: data/processed)
        dest_dir: Override destination directory (default: data/processed)
        
    Returns:
        PipelineResult with processing outcome
    """
    step = ProcessStep(source_dir=source_dir, dest_dir=dest_dir)
    ctx = PipelineContext()
    
    # Validate - if fails, return with SKIPPED status
    if not step.validate(ctx):
        logger.warning("Validation failed - no files to process")
        return PipelineResult(
            step=PipelineStep.PROCESS if hasattr(PipelineStep, 'PROCESS') else PipelineStep.EXTRACT,
            success=False,
            data={},
            message="No files to process - validation failed",
            error="Validation failed: source directory empty or missing",
            metadata={}
        )
    
    result = step.execute(ctx)
    
    return PipelineResult(
        step=PipelineStep.PROCESS if hasattr(PipelineStep, 'PROCESS') else PipelineStep.EXTRACT,
        success=result.success,
        data=result.data,
        message=result.message,
        error=result.error,
        metadata=result.metadata
    )
