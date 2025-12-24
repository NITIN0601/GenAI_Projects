"""
Advanced Table Merger for processed Excel files.

Merges tables within the same sheet that share identical row labels (Column A)
into a single horizontally-combined table.

Source: ./data/processed/
Destination: ./data/processed_advanced/
"""

import pandas as pd
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from openpyxl import load_workbook, Workbook
from openpyxl.utils import get_column_letter
from openpyxl.styles import Font, Alignment
from copy import copy

from src.utils import get_logger
from src.core import get_paths

logger = get_logger(__name__)


class TableMerger:
    """
    Merge tables with identical row labels within the same Excel sheet.
    
    Features:
    - Detects tables within a sheet that share the same Column A values
    - Merges horizontally (appends columns from matching tables)
    - Only merges if 100% row labels match (entire table must match)
    - Preserves column headers from each table
    """
    
    def __init__(self):
        """Initialize merger with paths."""
        self.paths = get_paths()
        self.source_dir = self.paths.data_dir / "processed"
        self.dest_dir = self.paths.data_dir / "processed_advanced"
        
        # Ensure destination exists
        self.dest_dir.mkdir(parents=True, exist_ok=True)
    
    def process_all_files(self) -> Dict[str, Any]:
        """
        Process all xlsx files in source directory.
        
        Returns:
            Dict with processing results
        """
        results = {
            'files_processed': 0,
            'files_with_merges': 0,
            'total_tables_merged': 0,
            'output_files': [],
            'errors': []
        }
        
        xlsx_files = list(self.source_dir.glob("*_tables.xlsx"))
        
        if not xlsx_files:
            logger.warning(f"No xlsx files found in {self.source_dir}")
            return results
        
        for xlsx_path in xlsx_files:
            # Skip temp files
            if xlsx_path.name.startswith('~$'):
                continue
                
            try:
                merge_result = self.process_file(xlsx_path)
                results['files_processed'] += 1
                
                if merge_result['tables_merged'] > 0:
                    results['files_with_merges'] += 1
                    results['total_tables_merged'] += merge_result['tables_merged']
                
                if merge_result['output_path']:
                    results['output_files'].append(merge_result['output_path'])
                    
            except Exception as e:
                logger.error(f"Error processing {xlsx_path}: {e}")
                results['errors'].append(f"{xlsx_path.name}: {str(e)}")
        
        return results
    
    def process_file(self, source_path: Path) -> Dict[str, Any]:
        """
        Process a single xlsx file.
        
        Args:
            source_path: Path to source xlsx file
            
        Returns:
            Dict with processing result
        """
        result = {
            'source': str(source_path),
            'output_path': None,
            'tables_merged': 0,
            'sheets_processed': 0
        }
        
        try:
            # Load workbook
            wb = load_workbook(source_path)
            
            # Process each sheet (skip Index)
            for sheet_name in wb.sheetnames:
                if sheet_name.lower() == 'index':
                    continue
                
                ws = wb[sheet_name]
                merge_count = self._process_sheet(ws, sheet_name)
                result['tables_merged'] += merge_count
                result['sheets_processed'] += 1
            
            # Save to destination
            output_path = self.dest_dir / source_path.name
            wb.save(output_path)
            result['output_path'] = str(output_path)
            
            logger.info(f"Processed {source_path.name}: {result['tables_merged']} merges across {result['sheets_processed']} sheets")
            
        except Exception as e:
            logger.error(f"Failed to process {source_path}: {e}")
            raise
        
        return result
    
    def _process_sheet(self, ws, sheet_name: str) -> int:
        """
        Process a single worksheet, merging tables with matching row labels.
        
        Args:
            ws: openpyxl Worksheet
            sheet_name: Name of sheet for logging
            
        Returns:
            Number of tables merged
        """
        # Find all table blocks in the sheet
        table_blocks = self._find_table_blocks(ws)
        
        if len(table_blocks) < 2:
            return 0  # Need at least 2 tables to merge
        
        logger.info(f"Sheet '{sheet_name}': Found {len(table_blocks)} table blocks")
        
        # Find groups of tables that can be merged (same row labels)
        mergeable_groups = self._find_mergeable_tables(table_blocks)
        
        merge_count = 0
        for group in mergeable_groups:
            if len(group) >= 2:
                logger.info(f"Sheet '{sheet_name}': Merging {len(group)} tables with {len(group[0]['row_labels'])} matching rows")
                self._merge_tables_horizontally(ws, group)
                merge_count += len(group) - 1  # Count of merged tables
        
        return merge_count
    
    def _find_table_blocks(self, ws) -> List[Dict[str, Any]]:
        """
        Find all table blocks in a worksheet.
        
        A table block:
        - Starts after a "Source:" row
        - Ends before the next metadata section (Row Header) or end of content
        
        Returns:
            List of table block dicts with start/end rows and row labels
        """
        blocks = []
        
        # First pass: find all Source: rows (they mark the end of metadata, start of table data)
        source_rows = []
        metadata_rows = []  # Track "Row Header" rows that start new metadata sections
        
        for row_num in range(1, ws.max_row + 1):
            cell_value = ws.cell(row=row_num, column=1).value
            if cell_value is None:
                continue
            
            cell_str = str(cell_value).strip()
            
            if cell_str.startswith('Source:'):
                source_rows.append(row_num)
            elif cell_str.startswith('Row Header'):
                metadata_rows.append(row_num)
        
        if not source_rows:
            return blocks
        
        # For each Source: row, find the table data range
        for i, source_row in enumerate(source_rows):
            # Table data starts after Source: row (skip completely empty rows)
            data_start = source_row + 1
            while data_start <= ws.max_row:
                # Check all columns for data (not just column 1)
                # This ensures we capture header rows like year rows that have empty col 1
                row_has_data = False
                for col in range(1, min(10, ws.max_column + 1)):
                    cell_val = ws.cell(row=data_start, column=col).value
                    if cell_val is not None and str(cell_val).strip():
                        row_has_data = True
                        break
                if row_has_data:
                    break
                data_start += 1
            
            if data_start > ws.max_row:
                continue
            
            # Table data ends before next metadata section or next Source/end of sheet
            data_end = ws.max_row
            
            # Find the next metadata section (Row Header) that comes after this source row
            for meta_row in metadata_rows:
                if meta_row > source_row:
                    data_end = meta_row - 1
                    break
            
            # Skip empty rows at the end
            while data_end > data_start:
                has_data = False
                for col in range(1, min(10, ws.max_column + 1)):
                    if ws.cell(row=data_end, column=col).value is not None:
                        has_data = True
                        break
                if has_data:
                    break
                data_end -= 1
            
            if data_end <= data_start:
                continue
            
            block = {
                'source_row': source_row,
                'start_row': data_start,
                'end_row': data_end,
                'row_labels': [],
                'header_row': data_start,  # First data row typically has headers like "$ in millions"
                'data_start_row': data_start  # Will be updated to skip header rows
            }
            
            # Detect header rows (rows with column headers like "$ in millions", date headers)
            # and data rows (rows with actual values)
            self._identify_header_and_data_rows(ws, block)
            
            # Extract row labels from data rows
            block['row_labels'] = self._extract_row_labels(ws, block)
            
            if block['row_labels']:  # Only add blocks with actual data
                blocks.append(block)
        
        return blocks
    
    def _identify_header_and_data_rows(self, ws, block: Dict) -> None:
        """
        Identify which rows are headers vs data in a table block.
        Updates block['data_start_row'] to point to first data row.
        
        Multi-level headers can include:
        - Year rows (e.g., "2024", "2023")
        - Date period rows (e.g., "Three Months Ended June 30,")
        - Currency unit rows (e.g., "$ in millions")
        - Empty header spacer rows
        """
        # Patterns that indicate a header row
        header_patterns = ['$ in millions', '$ in billions', '$ in thousands', 
                          'three months ended', 'six months ended', 'nine months ended',
                          'at june', 'at december', 'at march', 'at september',
                          'trading', 'fees', 'net interest', 'total']
        
        # Patterns that indicate this is NOT a header (actual data row labels)
        data_label_patterns = ['financing', 'execution', 'equity', 'fixed income',
                               'common', 'tangible', 'average', 'assets', 'liabilities',
                               'revenues', 'expenses', 'income', 'loss']
        
        data_start = block['start_row']
        header_rows_found = []
        
        for row_num in range(block['start_row'], min(block['start_row'] + 8, block['end_row'] + 1)):
            row_values = []
            first_col_value = None
            
            for col in range(1, min(10, ws.max_column + 1)):
                cell_val = ws.cell(row=row_num, column=col).value
                if cell_val:
                    row_values.append(str(cell_val).strip())
                    if col == 1:
                        first_col_value = str(cell_val).strip().lower()
            
            # Check if this is a data row (first column has data label)
            if first_col_value:
                is_data_label = any(pattern in first_col_value for pattern in data_label_patterns)
                if is_data_label:
                    # This is the start of data rows
                    data_start = row_num
                    break
            
            # Check if this is likely a header row
            is_header_row = False
            
            # Empty first column but has values in other columns = header row
            if not first_col_value and len(row_values) > 0:
                is_header_row = True
            
            # First column has header-like patterns
            if first_col_value:
                if any(pattern in first_col_value for pattern in header_patterns):
                    is_header_row = True
                # Check if first col is year (4 digits)
                if first_col_value.isdigit() and len(first_col_value) == 4:
                    is_header_row = True
            
            # Check if non-first columns have year values (e.g., "2024", "2023")
            year_count = sum(1 for v in row_values if v.isdigit() and len(v) == 4)
            if year_count >= 2:
                is_header_row = True
            
            if is_header_row:
                header_rows_found.append(row_num)
                data_start = row_num + 1
        
        block['header_rows'] = header_rows_found
        block['data_start_row'] = data_start
    
    def _extract_row_labels(self, ws, block: Dict) -> List[str]:
        """
        Extract row labels (Column A values) from a table block's data rows.
        
        Returns:
            List of row labels (normalized for comparison)
        """
        labels = []
        for row_num in range(block['data_start_row'], block['end_row'] + 1):
            val = ws.cell(row=row_num, column=1).value
            if val is not None:
                labels.append(str(val).strip())
            else:
                labels.append('')
        return labels
    
    def _find_mergeable_tables(self, blocks: List[Dict]) -> List[List[Dict]]:
        """
        Group table blocks that can be merged (identical row labels for entire table).
        
        Returns:
            List of groups, where each group is a list of mergeable blocks
        """
        if not blocks:
            return []
        
        groups = []
        used = set()
        
        for i, block_a in enumerate(blocks):
            if i in used:
                continue
            
            group = [block_a]
            used.add(i)
            
            for j, block_b in enumerate(blocks):
                if j in used:
                    continue
                
                if self._tables_match(block_a, block_b):
                    group.append(block_b)
                    used.add(j)
            
            if len(group) >= 2:
                groups.append(group)
        
        return groups
    
    def _tables_match(self, block_a: Dict, block_b: Dict) -> bool:
        """
        Check if two table blocks can be merged.
        
        Requirements:
        - Same number of row labels
        - 100% match of row labels (same text in same order)
        
        Returns:
            True if tables can be merged
        """
        labels_a = block_a['row_labels']
        labels_b = block_b['row_labels']
        
        if len(labels_a) != len(labels_b):
            return False
        
        if len(labels_a) == 0:
            return False
        
        for a, b in zip(labels_a, labels_b):
            # Normalize for comparison
            a_norm = a.lower().strip()
            b_norm = b.lower().strip()
            
            if a_norm != b_norm:
                return False
        
        return True
    
    def _merge_tables_horizontally(self, ws, blocks: List[Dict]) -> None:
        """
        Merge multiple table blocks horizontally in the worksheet.
        
        Process:
        1. Keep first table in place
        2. For each subsequent table, append its columns (except Column A) to the first table
        3. Clear the merged tables after copying
        
        Args:
            ws: openpyxl Worksheet
            blocks: List of table blocks to merge (must have matching row labels)
        """
        if len(blocks) < 2:
            return
        
        # Sort blocks by row position (first table stays in place)
        blocks = sorted(blocks, key=lambda b: b['start_row'])
        
        first_block = blocks[0]
        
        # Find the current rightmost column of the first block
        max_col = self._get_block_column_count(ws, first_block)
        insert_col = max_col + 1
        
        # Track existing columns in first block (for deduplication)
        # Key: tuple of column values, Value: column index
        existing_columns = self._extract_column_signatures(ws, first_block, 2, max_col)
        
        # Merge each subsequent block into the first
        for block in blocks[1:]:
            block_cols = self._get_block_column_count(ws, block)
            
            if block_cols <= 1:
                continue  # No data columns to copy
            
            # For each column in source block, check if it's a duplicate
            cols_to_copy = []  # List of (source_col_index, source_signature)
            
            for src_col in range(2, block_cols + 1):  # Skip column 1 (row labels)
                col_signature = self._get_column_signature(ws, block, src_col)
                
                # Check if this column already exists
                if col_signature not in existing_columns:
                    cols_to_copy.append((src_col, col_signature))
                    existing_columns[col_signature] = insert_col + len(cols_to_copy) - 1
                else:
                    logger.debug(f"Skipping duplicate column at {block['start_row']}, col {src_col}")
            
            if not cols_to_copy:
                # All columns are duplicates, skip this block
                self._clear_block(ws, block)
                continue
            
            # Copy only non-duplicate columns
            for copy_idx, (src_col, _) in enumerate(cols_to_copy):
                target_col = insert_col + copy_idx
                
                # Copy header rows
                for row_offset in range(block['start_row'], block['data_start_row']):
                    target_row = first_block['start_row'] + (row_offset - block['start_row'])
                    
                    try:
                        source_cell = ws.cell(row=row_offset, column=src_col)
                        target_cell = ws.cell(row=target_row, column=target_col)
                        
                        source_value = source_cell.value if hasattr(source_cell, 'value') else None
                        target_cell.value = source_value
                        self._copy_cell_style(source_cell, target_cell)
                    except AttributeError:
                        pass
                
                # Copy data rows
                for row_offset, src_row in enumerate(range(block['data_start_row'], block['end_row'] + 1)):
                    target_row = first_block['data_start_row'] + row_offset
                    
                    try:
                        source_cell = ws.cell(row=src_row, column=src_col)
                        target_cell = ws.cell(row=target_row, column=target_col)
                        
                        source_value = source_cell.value if hasattr(source_cell, 'value') else None
                        target_cell.value = source_value
                        self._copy_cell_style(source_cell, target_cell)
                    except AttributeError:
                        pass
            
            # Update insert column for next block
            insert_col += len(cols_to_copy)
            
            # Clear the merged block (to avoid duplicate data)
            self._clear_block(ws, block)
    
    def _extract_column_signatures(self, ws, block: Dict, start_col: int, end_col: int) -> Dict[tuple, int]:
        """
        Extract column signatures for all columns in a block.
        Returns dict mapping column signature (tuple of values) to column index.
        """
        signatures = {}
        for col in range(start_col, end_col + 1):
            sig = self._get_column_signature(ws, block, col)
            signatures[sig] = col
        return signatures
    
    def _get_column_signature(self, ws, block: Dict, col: int) -> tuple:
        """
        Get a signature (tuple of all values) for a column in a block.
        Includes header rows and data rows.
        """
        values = []
        
        # Include header row values
        for row_num in range(block['start_row'], block['data_start_row']):
            cell = ws.cell(row=row_num, column=col)
            val = cell.value if hasattr(cell, 'value') else None
            # Normalize value for comparison
            if val is not None:
                values.append(str(val).strip().lower())
            else:
                values.append('')
        
        # Include data row values
        for row_num in range(block['data_start_row'], block['end_row'] + 1):
            cell = ws.cell(row=row_num, column=col)
            val = cell.value if hasattr(cell, 'value') else None
            if val is not None:
                values.append(str(val).strip().lower())
            else:
                values.append('')
        
        return tuple(values)
    
    def _copy_cell_style(self, source_cell, target_cell) -> None:
        """Copy cell styling from source to target."""
        try:
            if source_cell.font:
                target_cell.font = copy(source_cell.font)
            if source_cell.alignment:
                target_cell.alignment = copy(source_cell.alignment)
            if source_cell.border:
                target_cell.border = copy(source_cell.border)
            if source_cell.fill:
                target_cell.fill = copy(source_cell.fill)
            if source_cell.number_format:
                target_cell.number_format = source_cell.number_format
        except Exception:
            pass  # Ignore style copy errors
    
    def _clear_block(self, ws, block: Dict) -> None:
        """Clear a table block after it has been merged."""
        # Clear from start_row to end_row (keep metadata above)
        for row_num in range(block['start_row'], block['end_row'] + 1):
            for col_num in range(1, ws.max_column + 1):
                try:
                    cell = ws.cell(row=row_num, column=col_num)
                    # Skip merged cells (they are read-only)
                    if hasattr(cell, 'value') and not isinstance(cell, type(None)):
                        cell.value = None
                except AttributeError:
                    pass  # MergedCell objects are read-only, skip them
    
    def _get_block_column_count(self, ws, block: Dict) -> int:
        """Get the number of columns with data in a table block."""
        max_col = 0
        for row_num in range(block['start_row'], block['end_row'] + 1):
            for col_num in range(1, ws.max_column + 1):
                if ws.cell(row=row_num, column=col_num).value is not None:
                    max_col = max(max_col, col_num)
        return max_col


# =============================================================================
# SINGLETON PATTERN
# =============================================================================

_merger_instance: Optional[TableMerger] = None


def get_table_merger() -> TableMerger:
    """Get or create TableMerger singleton instance."""
    global _merger_instance
    if _merger_instance is None:
        _merger_instance = TableMerger()
    return _merger_instance


def reset_table_merger() -> None:
    """Reset the merger singleton (for testing)."""
    global _merger_instance
    _merger_instance = None
