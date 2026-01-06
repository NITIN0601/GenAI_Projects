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

import re
from pathlib import Path
from typing import Dict, Any, Optional, List

from openpyxl import load_workbook
from openpyxl.cell.cell import MergedCell

from src.pipeline.base import StepInterface, StepResult, StepStatus, PipelineContext
from src.utils import get_logger
from src.utils.multi_row_header_normalizer import normalize_headers as normalize_multi_row_headers

# Import from modular sub-modules
from src.pipeline.steps.process.constants import TABLE_FILE_PATTERN
from src.pipeline.steps.process.table_finder import (
    find_all_tables,
    find_first_data_row_after_source,
)
from src.pipeline.steps.process.cell_processor import (
    process_cell_value,
    is_numeric_value,
)
from src.pipeline.steps.process.key_value_handler import (
    is_key_value_table,
    process_data_cells_only,
)
from src.pipeline.steps.process.header_flattener import flatten_table_headers_dynamic

logger = get_logger(__name__)


class ProcessStep(StepInterface):
    """
    Process step - normalize and clean extracted data.
    
    Implements StepInterface following pipeline pattern.
    
    Reads: data/extracted_raw/*.xlsx (output from extract step)
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
            source_dir: Override source directory (default: data/extracted_raw)
            dest_dir: Override destination directory (default: data/processed)
        """
        self.source_dir = source_dir
        self.dest_dir = dest_dir
    
    def validate(self, context: PipelineContext) -> bool:
        """Validate that source directory exists and has xlsx files."""
        from src.core import get_paths
        
        paths = get_paths()
        # Step 2: reads from extracted_raw (must match execute() source)
        source_path = Path(self.source_dir) if self.source_dir else Path(paths.data_dir) / "extracted_raw"
        
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
            "reads": ["data/extracted_raw/*.xlsx"],
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
    
    def _process_file(self, source_path: Path, dest_path: Path, stats: Dict) -> None:
        """Process a single xlsx file."""
        # Detect if this is a 10K (annual) report
        is_10k = '10k' in source_path.name.lower()
        
        wb = load_workbook(source_path)
        
        for sheet_name in wb.sheetnames:
            if sheet_name in ['Index', 'TOC', 'TOC_Sheet']:
                continue
            
            ws = wb[sheet_name]
            self._process_sheet(ws, stats, is_10k=is_10k)
        
        # Save to destination
        output_path = dest_path / source_path.name
        wb.save(output_path)
        wb.close()
        
        logger.debug(f"Processed {source_path.name} (is_10k={is_10k}) -> {output_path}")
    
    def _process_sheet(self, ws, stats: Dict, is_10k: bool = False) -> None:
        """
        Process a single worksheet - finds ALL tables dynamically and processes each.
        
        Tables are identified by "Table Title:" or "Source:" markers.
        Each table is processed independently for header flattening.
        
        Args:
            ws: Worksheet to process
            stats: Stats dictionary
            is_10k: True if this is from a 10K (annual) report
        """
        # === Check if this is a KEY-VALUE TABLE (should skip header processing) ===
        if is_key_value_table(ws):
            logger.debug("Skipping header processing for key-value table")
            process_data_cells_only(ws, stats, process_cell_value)
            return
        
        # === DYNAMIC TABLE DETECTION ===
        # Find all tables in the sheet by looking for "Source:" markers
        tables = find_all_tables(ws)
        
        if not tables:
            # Fall back to processing the whole sheet as one table
            # Dynamically find where data starts after Source(s): marker
            fallback_start = find_first_data_row_after_source(ws)
            tables = [{'start_row': fallback_start, 'end_row': ws.max_row, 'header_row': fallback_start}]
        
        logger.debug(f"Found {len(tables)} table(s) in sheet (is_10k={is_10k})")
        
        # Process each table independently
        for table_idx, table_info in enumerate(tables):
            self._process_single_table(ws, table_info, stats, is_10k=is_10k)
    
    def _process_single_table(
        self, 
        ws, 
        table_info: Dict, 
        stats: Dict, 
        is_10k: bool = False
    ) -> None:
        """
        Process a single table within the worksheet.
        
        Args:
            ws: The worksheet
            table_info: Dict with 'start_row', 'end_row', 'header_row', 'source_row'
            stats: Stats dict to update
            is_10k: True if this is from a 10K (annual) report
        """
        header_row = table_info.get('header_row', 13)
        end_row = table_info.get('end_row', ws.max_row)
        
        # PRE-SCAN: Normalize point-in-time headers ("At June 30, 2024" -> "Q2-2024")
        # This handles headers that appear BEFORE the detected header_row
        # (e.g., when a table has two sections with different header types)
        source_row = table_info.get('source_row', 11)
        for row_idx in range(source_row + 1, end_row + 1):
            for col_idx in range(1, min(ws.max_column + 1, 20)):  # Limit to first 20 columns
                cell = ws.cell(row=row_idx, column=col_idx)
                if cell.value:
                    val = str(cell.value).strip()
                    val_lower = val.lower()
                    
                    if val_lower.startswith('at ') or val_lower.startswith('as of '):
                        # Extract month and year using simple pattern matching
                        month_to_quarter = {
                            'january': 'Q1', 'february': 'Q1', 'march': 'Q1',
                            'april': 'Q2', 'may': 'Q2', 'june': 'Q2',
                            'july': 'Q3', 'august': 'Q3', 'september': 'Q3',
                            'october': 'Q4', 'november': 'Q4', 'december': 'Q4',
                        }
                        year_match = re.search(r'(20\d{2})', val)
                        detected_month = None
                        for month_name in month_to_quarter.keys():
                            if month_name in val_lower:
                                detected_month = month_name
                                break
                        
                        if detected_month and year_match:
                            quarter = month_to_quarter[detected_month]
                            normalized_val = f"{quarter}-{year_match.group(1)}"
                            cell.value = normalized_val
                            stats['cells_formatted'] = stats.get('cells_formatted', 0) + 1
        
        # Extract header rows (typically 1-4 rows starting from header_row)
        data_header_rows = []
        for offset in range(4):  # Check up to 4 header rows
            row_idx = header_row + offset
            if row_idx > end_row:
                break
            
            row_values = []
            for col_idx in range(1, ws.max_column + 1):
                cell = ws.cell(row=row_idx, column=col_idx)
                val = str(cell.value) if cell.value else ''
                
                # For 10K reports: Convert year-only headers to YTD-YYYY
                if is_10k and val.strip() and re.match(r'^20\d{2}$', val.strip()):
                    val = f"YTD-{val.strip()}"
                    # Also update the cell directly
                    cell.value = val
                    stats['cells_formatted'] = stats.get('cells_formatted', 0) + 1
                
                # Normalize point-in-time headers: "At June 30, 2024" -> "Q2-2024"
                # This catches headers that might be in rows before the detected header_row
                if val.strip():
                    val_lower = val.lower().strip()
                    if val_lower.startswith('at ') or val_lower.startswith('as of '):
                        # Extract month and year using simple pattern matching
                        month_to_quarter = {
                            'january': 'Q1', 'february': 'Q1', 'march': 'Q1',
                            'april': 'Q2', 'may': 'Q2', 'june': 'Q2',
                            'july': 'Q3', 'august': 'Q3', 'september': 'Q3',
                            'october': 'Q4', 'november': 'Q4', 'december': 'Q4',
                        }
                        year_match = re.search(r'(20\d{2})', val)
                        detected_month = None
                        for month_name in month_to_quarter.keys():
                            if month_name in val_lower:
                                detected_month = month_name
                                break
                        
                        if detected_month and year_match:
                            quarter = month_to_quarter[detected_month]
                            normalized_val = f"{quarter}-{year_match.group(1)}"
                            val = normalized_val
                            cell.value = normalized_val
                            stats['cells_formatted'] = stats.get('cells_formatted', 0) + 1
                
                row_values.append(val)
            
            # Check if this row has numeric data (means we've reached data rows)
            has_numeric = any(
                is_numeric_value(v) for v in row_values[1:5] if v
            )
            if has_numeric:
                break
            
            # Check if row has any content
            if any(row_values[1:]):
                data_header_rows.append(row_values)
        
        if not data_header_rows:
            return
        
        # Normalize headers
        source_filename = ''
        if hasattr(ws, 'parent') and hasattr(ws.parent, 'path') and ws.parent.path:
            source_filename = str(ws.parent.path)
        
        normalized = normalize_multi_row_headers(data_header_rows, source_filename)
        
        # Extract normalized headers
        l1_per_column = normalized.get('l1_headers', [])
        normalized_headers = normalized.get('normalized_headers', [])
        
        # For 10K reports: Update normalized_headers with YTD- prefix for year-only values
        if is_10k:
            for i, val in enumerate(normalized_headers):
                if val and re.match(r'^20\d{2}$', val.strip()):
                    normalized_headers[i] = f"YTD-{val.strip()}"
        
        num_cols = ws.max_column
        
        def safe_set_cell_value(ws, row: int, col: int, value: Any) -> bool:
            """Safely set cell value, skipping merged cells."""
            cell = ws.cell(row=row, column=col)
            if not isinstance(cell, MergedCell):
                cell.value = value
                return True
            return False
        
        # === REPLACE actual data header rows with normalized Y/Q codes ===
        # Use dynamic row numbers based on header_row
        # For multi-row headers: put normalized code in first row, clear second row
        if len(data_header_rows) >= 1:
            for col_idx in range(2, num_cols + 1):
                norm_val = normalized_headers[col_idx - 1] if col_idx - 1 < len(normalized_headers) else ''
                
                # Always apply normalized code if it's a valid date code
                # Valid codes: Q1-2024, Q2-QTD-2024, Q3-YTD-2024, YTD-2024
                if norm_val:
                    is_valid_code = (
                        re.match(r'^Q[1-4](-QTD|-YTD)?-20\d{2}', norm_val) or
                        re.match(r'^YTD-20\d{2}', norm_val)
                    )
                    if is_valid_code:
                        if safe_set_cell_value(ws, header_row, col_idx, norm_val):
                            stats['cells_formatted'] = stats.get('cells_formatted', 0) + 1
        
        # Clear second header row for multi-row headers to prevent duplicates
        # The normalized code is now in row 1, row 2 should be empty or cleared
        if len(data_header_rows) > 1:
            for col_idx in range(2, num_cols + 1):
                orig_row2_val = data_header_rows[1][col_idx - 1] if col_idx - 1 < len(data_header_rows[1]) else ''
                norm_val = normalized_headers[col_idx - 1] if col_idx - 1 < len(normalized_headers) else ''
                
                # If row 2 has a year (e.g., '2024') and we have a normalized code,
                # clear row 2 since the full code is now in row 1
                if orig_row2_val and norm_val:
                    orig_str = str(orig_row2_val).strip()
                    is_year_only = re.match(r'^20\d{2}$', orig_str)
                    is_valid_code = (
                        re.match(r'^Q[1-4](-QTD|-YTD)?-20\d{2}', norm_val) or
                        re.match(r'^YTD-20\d{2}', norm_val)
                    )
                    if is_year_only and is_valid_code:
                        # Clear the year from row 2 since it's merged into row 1
                        safe_set_cell_value(ws, header_row + 1, col_idx, None)
                        stats['cells_formatted'] = stats.get('cells_formatted', 0) + 1
        
        # === FLATTEN HEADERS for this table ===
        flatten_table_headers_dynamic(ws, header_row, data_header_rows, normalized_headers, stats)
        
        # Process data cells for this table
        data_start = header_row + len(data_header_rows) + 1  # After headers + empty separator
        for row_idx in range(data_start, end_row + 1):
            # === DETECT AND NORMALIZE MID-TABLE HEADERS ===
            # Mid-table headers have empty/unit first col but date patterns in other cols
            first_cell = ws.cell(row_idx, 1).value
            first_val = str(first_cell).strip().lower() if first_cell else ''
            is_mid_table_header = first_val in ['', 'nan', 'none'] or first_val.startswith('$')
            
            if is_mid_table_header:
                # Check if this row has date patterns in columns 2+
                mid_header_row = []
                for col_idx in range(1, min(ws.max_column + 1, 15)):
                    cell_val = ws.cell(row_idx, col_idx).value
                    mid_header_row.append(str(cell_val) if cell_val else '')
                
                # If we find date patterns, try to normalize
                has_date_pattern = any(
                    any(kw in str(v).lower() for kw in ['months ended', 'at ', 'as of', 'june', 'march', 'september', 'december'])
                    for v in mid_header_row[1:5] if v
                )
                
                if has_date_pattern:
                    # Check if next row contains year values (e.g., '2024', '2023')
                    # Multi-row headers have period in current row, year in next row
                    header_rows_to_normalize = [mid_header_row]
                    
                    if row_idx + 1 <= end_row:
                        next_row = []
                        for col_idx in range(1, min(ws.max_column + 1, 15)):
                            cell_val = ws.cell(row_idx + 1, col_idx).value
                            next_row.append(str(cell_val) if cell_val else '')
                        
                        # Check if next row has year values (4-digit years like 2024, 2023)
                        has_year = any(
                            re.match(r'^20\d{2}$', str(v).strip()) 
                            for v in next_row[1:5] if v
                        )
                        if has_year:
                            header_rows_to_normalize.append(next_row)
                    
                    # Normalize using multi_row_header_normalizer
                    mid_normalized = normalize_multi_row_headers(header_rows_to_normalize, source_filename)
                    mid_norm_headers = mid_normalized.get('normalized_headers', [])
                    
                    # Write normalized values back to cells (first row gets the codes)
                    for col_idx in range(2, min(len(mid_norm_headers) + 1, ws.max_column + 1)):
                        norm_val = mid_norm_headers[col_idx - 1] if col_idx - 1 < len(mid_norm_headers) else ''
                        if norm_val:
                            is_valid_code = (
                                re.match(r'^Q[1-4](-QTD|-YTD)?-20\d{2}', norm_val) or
                                re.match(r'^YTD-20\d{2}', norm_val)
                            )
                            if is_valid_code:
                                if safe_set_cell_value(ws, row_idx, col_idx, norm_val):
                                    stats['cells_formatted'] = stats.get('cells_formatted', 0) + 1
                                # Clear year from next row if we used it
                                if len(header_rows_to_normalize) > 1:
                                    safe_set_cell_value(ws, row_idx + 1, col_idx, None)
                    continue  # Move to next row after normalizing header
            
            # Process regular data cells
            for col_idx in range(1, ws.max_column + 1):
                cell = ws.cell(row_idx, col_idx)
                if cell.value is None:
                    continue
                
                original_value = cell.value
                new_value, cell_format = process_cell_value(original_value, row_idx, col_idx)
                
                if new_value != original_value:
                    cell.value = new_value
                    stats['cells_formatted'] = stats.get('cells_formatted', 0) + 1
                
                if cell_format:
                    cell.number_format = cell_format
