"""
Advanced Table Merger for processed Excel files.

Merges tables within the same sheet that share identical row labels (Column A)
into a single horizontally-combined table with multi-level headers preserved.

Source: ./data/processed/
Destination: ./data/processed_advanced/
"""

import pandas as pd
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from openpyxl import load_workbook, Workbook
from openpyxl.utils import get_column_letter
from openpyxl.styles import Font, Alignment
import re

from src.utils import get_logger
from src.core import get_paths

logger = get_logger(__name__)


class TableMerger:
    """
    Merge tables with identical row labels within the same Excel sheet.
    
    Features:
    - Detects tables within a sheet that share the same Column A values
    - Merges horizontally (appends columns)
    - Preserves multi-level headers (L1, L2)
    - Only merges if 100% row label match
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
                merge_count = self._process_sheet(ws)
                result['tables_merged'] += merge_count
                result['sheets_processed'] += 1
                
                # Insert metadata headers before sub-tables
                self._insert_subtable_headers(ws)
                
                # Fix split headers (e.g. "At December" | "2024")
                self._fix_split_headers(ws)
                
                # Insert empty rows before repeated period headers
                self._insert_period_separators(ws)
            
            # Save to destination
            output_path = self.dest_dir / source_path.name
            wb.save(output_path)
            result['output_path'] = str(output_path)
            
            logger.info(f"Processed {source_path.name}: {result['tables_merged']} merges")
            
        except Exception as e:
            logger.error(f"Failed to process {source_path}: {e}")
            raise
        
        return result
    
        return result
    
    def _fix_split_headers(self, ws) -> None:
        """
        Merge split header cells like "At December" | "2024" -> "At December 2024" | "".
        Logic:
        1. Iterate through first few rows (header area).
        2. Look for date-related patterns in one cell and Year in the next.
        3. Merge content into left cell and clear right cell.
        """
        HEADER_ROWS = 5
        DATE_PREFIXES = ['at december', 'at september', 'at march', 'at june', 'ended']
        
        for row in range(1, min(ws.max_row + 1, HEADER_ROWS + 1)):
            for col in range(1, ws.max_column): # up to second to last column
                curr_cell = ws.cell(row=row, column=col)
                next_cell = ws.cell(row=row, column=col+1)
                
                curr_val = str(curr_cell.value).strip().lower() if curr_cell.value else ""
                next_val = str(next_cell.value).strip() if next_cell.value else ""
                
                # Check pattern: "At December" + "2024"
                if any(prefix in curr_val for prefix in DATE_PREFIXES):
                    # Check if next cell is a year (4 digits, maybe footnote)
                    if re.match(r'^\d{4}', next_val):
                        # Merge
                        merged_val = f"{curr_cell.value} {next_cell.value}"
                        curr_cell.value = merged_val
                        next_cell.value = None
                        logger.info(f"Merged split header at {curr_cell.coordinate}: '{merged_val}'")

    def _insert_period_separators(self, ws) -> None:
        """
        Insert empty row before second occurrence of period headers.
        
        Detects patterns like:
        - "Three Months Ended"
        - "Six Months Ended"
        - "Nine Months Ended"
        
        When seen for the 2nd+ time in a sheet, inserts an empty row above.
        """
        PERIOD_PATTERNS = [
            'three months ended',
            'six months ended',
            'nine months ended',
        ]
        
        # Find all rows with period headers
        period_rows = []
        for row_num in range(1, ws.max_row + 1):
            for col_num in range(1, min(ws.max_column + 1, 10)):  # Check first 10 columns
                cell_value = ws.cell(row=row_num, column=col_num).value
                if cell_value:
                    cell_lower = str(cell_value).lower().strip()
                    if any(pattern in cell_lower for pattern in PERIOD_PATTERNS):
                        period_rows.append(row_num)
                        break  # Only count once per row
        
        # Insert empty rows before 2nd, 3rd, etc. occurrences (work backwards to avoid row shift issues)
        if len(period_rows) >= 2:
            rows_to_insert = period_rows[1:]  # Skip first occurrence
            rows_to_insert.sort(reverse=True)  # Insert from bottom up
            
            for row_num in rows_to_insert:
                ws.insert_rows(row_num)
    
    def _insert_subtable_headers(self, ws) -> None:
        """
        Insert metadata header block before sub-tables starting with '$ in billions/millions'.
        
        When detecting a second "$ in billions" or "$ in millions" row, insert:
        - Empty row
        - Row Header (Level 1):
        - Row Header (Level 2):
        - Product/Entity:
        - Column Header (Level 1):
        - Column Header (Level 2):
        - Year(s):
        - Empty row
        - Table Title:
        - Source:
        """
        SUBTABLE_PATTERNS = [
            '$ in billions',
            '$ in millions',
            '$ in thousands',
        ]
        
        # Find all rows with sub-table headers
        subtable_rows = []
        for row_num in range(1, ws.max_row + 1):
            # Check first 3 columns to be safe
            for col_num in range(1, 4):
                cell_value = ws.cell(row=row_num, column=col_num).value
                if cell_value:
                    cell_str = str(cell_value).strip().lower()
                    # Use 'in' check instead of startswith to handle slight variations/junk chars
                    if any(pattern in cell_str for pattern in SUBTABLE_PATTERNS):
                        subtable_rows.append(row_num)
                        break

        
        # Only process if there are 2+ sub-tables
        if len(subtable_rows) < 2:
            return
        
        # Get original table metadata from top of sheet
        original_table_title = ""
        original_source = ""
        for row_num in range(1, min(20, ws.max_row + 1)):
            cell_value = ws.cell(row=row_num, column=1).value
            if cell_value:
                cell_str = str(cell_value).strip()
                if cell_str.startswith('Table Title:'):
                    original_table_title = cell_str
                elif cell_str.startswith('Source:'):
                    original_source = cell_str
        
        # Metadata block to insert (11 rows)
        metadata_block = [
            "",  # Empty row
            "Row Header (Level 1):",
            "Row Header (Level 2):",
            "Product/Entity:",
            "Column Header (Level 1):",
            "Column Header (Level 2):",
            "Year(s):",
            "",  # Empty row
            original_table_title or "Table Title:",
            original_source or "Source:",
        ]
        
        # Insert before 2nd, 3rd, etc. sub-tables (work backwards)
        rows_to_process = subtable_rows[1:]  # Skip first occurrence
        rows_to_process.sort(reverse=True)  # Insert from bottom up
        
        for row_num in rows_to_process:
            # Insert empty rows for metadata block
            ws.insert_rows(row_num, len(metadata_block))
            
            # Fill in metadata values
            for i, metadata_value in enumerate(metadata_block):
                ws.cell(row=row_num + i, column=1).value = metadata_value
    
    def _process_sheet(self, ws) -> int:
        """
        Process a single worksheet, merging tables with matching row labels.
        
        Args:
            ws: openpyxl Worksheet
            
        Returns:
            Number of tables merged
        """
        # Find all table blocks in the sheet
        table_blocks = self._find_table_blocks(ws)
        
        if len(table_blocks) < 2:
            return 0  # Need at least 2 tables to merge
        
        # Check if tables can be merged (same row labels)
        mergeable_groups = self._find_mergeable_tables(table_blocks)
        
        merge_count = 0
        for group in mergeable_groups:
            if len(group) >= 2:
                self._merge_tables_in_sheet(ws, group)
                merge_count += len(group) - 1  # Count of merged tables
        
        return merge_count
    
    def _find_table_blocks(self, ws) -> List[Dict[str, Any]]:
        """
        Find all table blocks in a worksheet.
        
        A table block starts after a "Source:" row and ends before the next
        metadata section or end of content.
        
        Returns:
            List of table block dicts with start/end rows and data
        """
        blocks = []
        current_block = None
        
        for row_num in range(1, ws.max_row + 1):
            cell_value = ws.cell(row=row_num, column=1).value
            
            if cell_value is None:
                continue
            
            cell_str = str(cell_value).strip()
            
            # Detect start of a table data section
            if cell_str.startswith('Source:'):
                # The table data starts after this row
                if current_block is not None:
                    current_block['end_row'] = row_num - 1
                    if current_block['end_row'] > current_block['start_row']:
                        blocks.append(current_block)
                
                current_block = {
                    'source_row': row_num,
                    'start_row': row_num + 1,  # Data starts after Source
                    'end_row': None,
                    'header_rows': [],
                    'data_rows': []
                }
            
            # Detect metadata rows that indicate end of table data
            elif current_block is not None and any(cell_str.startswith(prefix) for prefix in [
                'Row Header', 'Column Header', 'Product/Entity', 'Year(s):', 'Table Title:'
            ]):
                # This is metadata for a new table - close current block
                if current_block['end_row'] is None:
                    current_block['end_row'] = row_num - 1
                    if current_block['end_row'] > current_block['start_row']:
                        blocks.append(current_block)
                    current_block = None
        
        # Close last block
        if current_block is not None and current_block['end_row'] is None:
            current_block['end_row'] = ws.max_row
            if current_block['end_row'] > current_block['start_row']:
                blocks.append(current_block)
        
        # Extract row labels for each block
        for block in blocks:
            block['row_labels'] = self._extract_row_labels(ws, block)
        
        return blocks
    
    def _extract_row_labels(self, ws, block: Dict) -> List[str]:
        """Extract row labels (Column A values) from a table block."""
        labels = []
        for row_num in range(block['start_row'], block['end_row'] + 1):
            val = ws.cell(row=row_num, column=1).value
            if val is not None:
                labels.append(str(val).strip())
            else:
                labels.append('')
        return labels
    
    def _find_mergeable_tables(self, blocks: List[Dict]) -> List[List[Dict]]:
        """
        Group table blocks that can be merged (identical row labels).
        
        Returns:
            List of groups, where each group is a list of mergeable blocks
        """
        if not blocks:
            return []
        
        # Simple approach: check if all blocks have the same row labels
        # For more complex scenarios, we could use fuzzy matching
        
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
                
                if self._labels_match(block_a['row_labels'], block_b['row_labels']):
                    group.append(block_b)
                    used.add(j)
            
            if len(group) >= 2:
                groups.append(group)
        
        return groups
    
    def _labels_match(self, labels_a: List[str], labels_b: List[str]) -> bool:
        """
        Check if two sets of row labels match for merging.
        
        Requires 100% match (same labels in same order).
        """
        if len(labels_a) != len(labels_b):
            return False
        
        for a, b in zip(labels_a, labels_b):
            # Normalize for comparison
            a_norm = a.lower().strip()
            b_norm = b.lower().strip()
            
            if a_norm != b_norm:
                return False
        
        return True
    
    def _merge_tables_in_sheet(self, ws, blocks: List[Dict]) -> None:
        """
        Merge multiple table blocks horizontally in the worksheet.
        
        The first block's data is kept in place.
        Subsequent blocks' columns (except Column A) are appended to the first block.
        The subsequent blocks are then cleared.
        """
        if len(blocks) < 2:
            return
        
        # Sort blocks by row position
        blocks = sorted(blocks, key=lambda b: b['start_row'])
        
        first_block = blocks[0]
        
        # Find the rightmost column of the first block
        first_block_end_col = ws.max_column  # We'll calculate more precisely
        
        # For simplicity, iterate through all rows of first block to find max col
        max_col = 1
        for row_num in range(first_block['start_row'], first_block['end_row'] + 1):
            for col_num in range(1, ws.max_column + 1):
                if ws.cell(row=row_num, column=col_num).value is not None:
                    max_col = max(max_col, col_num)
        
        insert_col = max_col + 1
        
        # Merge each subsequent block
        for block in blocks[1:]:
            # Get number of columns to copy (skip first column which is row label)
            block_cols = self._get_block_column_count(ws, block)
            
            if block_cols <= 1:
                continue
            
            # Copy columns 2+ from this block to the end of first block
            for row_offset, row_num in enumerate(range(block['start_row'], block['end_row'] + 1)):
                target_row = first_block['start_row'] + row_offset
                
                for col_offset in range(1, block_cols):  # Skip column 1 (row labels)
                    source_col = col_offset + 1
                    target_col = insert_col + col_offset - 1
                    
                    # Copy value
                    source_val = ws.cell(row=row_num, column=source_col).value
                    ws.cell(row=target_row, column=target_col).value = source_val
                    
                    # Copy style if needed (simplified)
                    source_cell = ws.cell(row=row_num, column=source_col)
                    target_cell = ws.cell(row=target_row, column=target_col)
                    if source_cell.font:
                        target_cell.font = source_cell.font.copy()
                    if source_cell.alignment:
                        target_cell.alignment = source_cell.alignment.copy()
            
            # Update insert position for next block
            insert_col += block_cols - 1
            
            # Clear the merged block (optional - keeps sheet cleaner)
            # For now, we'll leave it as-is to preserve the original structure
    
    def _get_block_column_count(self, ws, block: Dict) -> int:
        """Get the number of columns in a table block."""
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
