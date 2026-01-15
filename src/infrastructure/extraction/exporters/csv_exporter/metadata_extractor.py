"""
Metadata Extractor for Excel Table Sheets.

Extracts metadata blocks from Excel sheets containing one or more tables.
Handles both full metadata blocks and minimal (Title + Source only) blocks.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any

import pandas as pd

from src.utils import get_logger
from src.utils.metadata_labels import MetadataLabels
from .constants import (
    TableDetectionPatterns,
    MetadataColumnMapping,
    CSVExportSettings,
)

logger = get_logger(__name__)


@dataclass
class TableBlock:
    """
    Represents a single table within a sheet.
    
    A sheet may contain multiple tables, each with its own
    metadata block and data rows.
    """
    
    # Table position within the sheet (1-indexed)
    table_index: int
    
    # Extracted metadata as key-value pairs
    metadata: Dict[str, str] = field(default_factory=dict)
    
    # Row indices (0-indexed, inclusive)
    metadata_start_row: int = 0
    metadata_end_row: int = 0
    data_start_row: int = 0
    data_end_row: int = 0
    
    # Extracted data as DataFrame (header + data rows)
    data_df: Optional[pd.DataFrame] = None
    
    # Validation flags
    has_title: bool = False
    has_source: bool = False
    
    @property
    def is_valid(self) -> bool:
        """Check if table has mandatory fields."""
        return self.has_title and self.has_source
    
    @property
    def row_count(self) -> int:
        """Number of data rows (excluding header)."""
        if self.data_df is None:
            return 0
        return max(0, len(self.data_df) - 1)  # Subtract header row


class SheetMetadataExtractor:
    """
    Extracts metadata blocks from Excel table sheets.
    
    Handles:
    - Single-table sheets with full metadata
    - Multi-table sheets with full or minimal metadata per table
    - Missing/optional metadata fields
    - Mandatory field validation
    """
    
    def __init__(self):
        self.logger = get_logger(f"{__name__}.{self.__class__.__name__}")
    
    def extract_all_tables(
        self, 
        sheet_df: pd.DataFrame,
        sheet_name: str = ""
    ) -> List[TableBlock]:
        """
        Parse sheet and extract all table blocks.
        
        Args:
            sheet_df: DataFrame of the entire sheet (no header)
            sheet_name: Sheet name for logging
            
        Returns:
            List of TableBlock, one per table in the sheet
        """
        if sheet_df.empty:
            self.logger.debug(f"Sheet '{sheet_name}' is empty")
            return []
        
        # Detect primary table boundaries using "Table Title:" markers
        primary_boundaries = self._detect_table_boundaries(sheet_df)
        
        if not primary_boundaries:
            self.logger.warning(f"No tables found in sheet '{sheet_name}'")
            return []
        
        # For each primary table, check if it contains sub-tables
        all_boundaries = []
        for meta_start, meta_end, data_start, data_end in primary_boundaries:
            # Check for sub-tables within this data region
            sub_boundaries = self._detect_sub_table_boundaries(
                sheet_df, 
                meta_start, 
                meta_end,
                data_start, 
                data_end
            )
            
            if sub_boundaries and len(sub_boundaries) > 1:
                # Multiple sub-tables found - use sub-table boundaries
                all_boundaries.extend(sub_boundaries)
                self.logger.debug(
                    f"Sheet '{sheet_name}': Split table into {len(sub_boundaries)} sub-tables"
                )
            else:
                # Single table or no sub-tables detected
                all_boundaries.append((meta_start, meta_end, data_start, data_end))
        
        self.logger.debug(f"Found {len(all_boundaries)} table(s) in sheet '{sheet_name}'")
        
        # Extract each table
        tables = []
        for idx, (meta_start, meta_end, data_start, data_end) in enumerate(all_boundaries, start=1):
            table = self._extract_single_table(
                sheet_df=sheet_df,
                table_index=idx,
                metadata_start=meta_start,
                metadata_end=meta_end,
                data_start=data_start,
                data_end=data_end,
                sheet_name=sheet_name
            )
            tables.append(table)
        
        return tables
    
    def _detect_table_boundaries(
        self, 
        sheet_df: pd.DataFrame
    ) -> List[Tuple[int, int, int, int]]:
        """
        Detect table boundaries using 'Table Title:' markers.
        
        Returns:
            List of (metadata_start, metadata_end, data_start, data_end) tuples
            All indices are 0-indexed row numbers in the DataFrame.
        """
        boundaries = []
        first_col = sheet_df.iloc[:, 0].fillna('').astype(str)
        
        # Find all "Table Title:" occurrences
        title_rows = []
        for row_idx, val in enumerate(first_col):
            if val.startswith(TableDetectionPatterns.TABLE_TITLE_MARKER):
                title_rows.append(row_idx)
        
        if not title_rows:
            return []
        
        # For each Table Title, find the corresponding boundaries
        for i, title_row in enumerate(title_rows):
            # Metadata start: search backward for metadata block start
            meta_start = self._find_metadata_start(first_col, title_row)
            
            # Metadata end: find Source(s) row (typically right after Title)
            meta_end = self._find_source_row(first_col, title_row)
            
            # Data start: first non-empty, non-metadata row after meta_end
            data_start = self._find_data_start(first_col, meta_end)
            
            # Data end: either next table's meta_start - 1, or end of sheet
            if i + 1 < len(title_rows):
                next_meta_start = self._find_metadata_start(first_col, title_rows[i + 1])
                # Find last non-empty row before next metadata
                data_end = self._find_data_end(first_col, data_start, next_meta_start)
            else:
                # Last table - data goes to end of sheet
                data_end = self._find_data_end(first_col, data_start, len(first_col))
            
            boundaries.append((meta_start, meta_end, data_start, data_end))
        
        return boundaries
    
    def _find_metadata_start(self, first_col: pd.Series, title_row: int) -> int:
        """Find the start of metadata block by searching backward from title row."""
        # Search backward for known metadata prefixes or back link
        for row in range(title_row - 1, -1, -1):
            val = first_col.iloc[row]
            
            # Stop if we hit a previous table's data (non-metadata, non-empty)
            if val and not self._is_metadata_prefix(val):
                # Check if it's just a blank separator
                if val.strip():
                    return row + 1
            
            # Stop if we hit the back link (start of metadata block)
            if val.startswith('← Back to Index'):
                return row
            
            # Safety: don't search too far back
            if title_row - row > TableDetectionPatterns.MAX_METADATA_ROWS:
                return row
        
        return 0
    
    def _find_source_row(self, first_col: pd.Series, title_row: int) -> int:
        """Find Source(s) row after title row."""
        for row in range(title_row + 1, min(title_row + 5, len(first_col))):
            val = first_col.iloc[row]
            if MetadataLabels.is_sources(val):
                return row
        # If not found, return title row
        return title_row
    
    def _find_data_start(self, first_col: pd.Series, meta_end: int) -> int:
        """Find first data row after metadata block."""
        for row in range(meta_end + 1, len(first_col)):
            val = first_col.iloc[row].strip()
            if val and not self._is_metadata_prefix(val):
                return row
        return meta_end + 1
    
    def _find_data_end(self, first_col: pd.Series, data_start: int, limit: int) -> int:
        """Find last non-empty data row before limit."""
        last_non_empty = data_start
        for row in range(data_start, limit):
            val = first_col.iloc[row].strip()
            # Stop if we hit next metadata block
            if self._is_metadata_prefix(val):
                break
            if val:
                last_non_empty = row
        return last_non_empty
    
    def _is_metadata_prefix(self, val: str) -> bool:
        """Check if value starts with a known metadata prefix."""
        if not val:
            return False
        return any(val.startswith(p) for p in TableDetectionPatterns.METADATA_PREFIXES)
    
    def _is_sub_table_header(self, val: str) -> bool:
        """Check if value is a sub-table data header pattern like '$ in millions'."""
        if not val:
            return False
        val_stripped = val.strip()
        return any(
            val_stripped.startswith(p) or val_stripped == p 
            for p in TableDetectionPatterns.SUB_TABLE_HEADER_PATTERNS
        )
    
    def _detect_sub_table_boundaries(
        self,
        sheet_df: pd.DataFrame,
        meta_start: int,
        meta_end: int,
        data_start: int,
        data_end: int
    ) -> List[Tuple[int, int, int, int]]:
        """
        Detect sub-tables within a single logical table.
        
        Sub-tables are data blocks separated by blank rows, each starting
        with a data header row (e.g., "$ in millions"). They share the same
        metadata block from the parent table.
        
        Note: Multi-row category headers above the data header are NOT included
        as they are normalized manually elsewhere.
        
        Args:
            sheet_df: The full sheet DataFrame
            meta_start: Start row of metadata block
            meta_end: End row of metadata block
            data_start: Start row of data region
            data_end: End row of data region
            
        Returns:
            List of (metadata_start, metadata_end, sub_data_start, sub_data_end) tuples
            Returns empty list or single-element list if no sub-tables detected.
        """
        first_col = sheet_df.iloc[:, 0].fillna('').astype(str)
        
        # Find all sub-table header rows within the data region
        sub_header_rows = []
        for row in range(data_start, data_end + 1):
            val = first_col.iloc[row]
            if self._is_sub_table_header(val):
                sub_header_rows.append(row)
        
        # If only 0 or 1 header found, no sub-tables - return empty
        if len(sub_header_rows) <= 1:
            return []
        
        # Build boundaries for each sub-table
        sub_boundaries = []
        for i, header_row in enumerate(sub_header_rows):
            # Sub-table starts at the data header row (e.g., "$ in millions")
            sub_data_start = header_row
            
            # Sub-table data ends at the row before the next sub-table header,
            # or at the end of the data region
            if i + 1 < len(sub_header_rows):
                next_header = sub_header_rows[i + 1]
                # Find last non-empty row before next header
                sub_data_end = next_header - 1
                while sub_data_end > sub_data_start:
                    val = first_col.iloc[sub_data_end].strip()
                    if val and not self._is_metadata_prefix(val):
                        break
                    sub_data_end -= 1
            else:
                sub_data_end = data_end
            
            # Validate sub-table has enough data rows
            row_count = sub_data_end - sub_data_start + 1
            if row_count >= TableDetectionPatterns.MIN_SUB_TABLE_DATA_ROWS:
                # All sub-tables share the parent's metadata block
                sub_boundaries.append((
                    meta_start,
                    meta_end,
                    sub_data_start,
                    sub_data_end
                ))
        
        return sub_boundaries
    
    def _extract_single_table(
        self,
        sheet_df: pd.DataFrame,
        table_index: int,
        metadata_start: int,
        metadata_end: int,
        data_start: int,
        data_end: int,
        sheet_name: str
    ) -> TableBlock:
        """Extract a single table block from the sheet."""
        table = TableBlock(
            table_index=table_index,
            metadata_start_row=metadata_start,
            metadata_end_row=metadata_end,
            data_start_row=data_start,
            data_end_row=data_end,
        )
        
        # Parse metadata block
        table.metadata = self._parse_metadata_block(
            sheet_df, 
            metadata_start, 
            metadata_end
        )
        
        # Check mandatory fields
        table.has_title = bool(table.metadata.get('Table_Title_Metadata', '').strip())
        table.has_source = bool(table.metadata.get('Sources_Metadata', '').strip())
        
        # Apply fallbacks for missing mandatory fields
        if not table.has_title:
            table.metadata['Table_Title_Metadata'] = CSVExportSettings.DEFAULT_TABLE_TITLE
            self.logger.warning(
                f"Sheet '{sheet_name}' table {table_index}: Missing Table Title, using default"
            )
        
        if not table.has_source:
            table.metadata['Sources_Metadata'] = CSVExportSettings.DEFAULT_SOURCE
            self.logger.warning(
                f"Sheet '{sheet_name}' table {table_index}: Missing Source(s), using default"
            )
        
        # Extract data rows
        if data_start <= data_end:
            table.data_df = sheet_df.iloc[data_start:data_end + 1].copy()
            table.data_df.reset_index(drop=True, inplace=True)
        
        return table
    
    def _parse_metadata_block(
        self, 
        sheet_df: pd.DataFrame, 
        start_row: int, 
        end_row: int
    ) -> Dict[str, str]:
        """
        Parse metadata from a block of rows.
        
        Returns:
            Dict with standardized column names as keys.
        """
        metadata = {col: '' for col in MetadataColumnMapping.METADATA_COLUMNS}
        
        # Column header components (to be combined later)
        header_l1 = ''
        header_l2 = ''
        header_l3 = ''
        
        for row in range(start_row, min(end_row + 3, len(sheet_df))):  # +3 to catch Source(s)
            if row >= len(sheet_df):
                break
                
            first_cell = str(sheet_df.iloc[row, 0]) if pd.notna(sheet_df.iloc[row, 0]) else ''
            
            # Skip empty rows
            if not first_cell.strip():
                continue
            
            # Parse based on prefix
            for label, column in MetadataColumnMapping.LABEL_TO_COLUMN.items():
                if first_cell.startswith(label):
                    # Extract value (everything after the label)
                    value = first_cell[len(label):].strip()
                    
                    # Also check subsequent columns for values
                    row_values = []
                    for col_idx in range(sheet_df.shape[1]):
                        cell = sheet_df.iloc[row, col_idx]
                        if pd.notna(cell):
                            cell_str = str(cell).strip()
                            # Skip the label itself
                            if col_idx == 0 and cell_str.startswith(label):
                                cell_str = cell_str[len(label):].strip()
                            if cell_str:
                                row_values.append(cell_str)
                    
                    combined_value = ', '.join(row_values) if row_values else value
                    
                    # Handle column header levels specially
                    if 'Column_Header_L1' in column:
                        header_l1 = combined_value
                    elif 'Column_Header_L2' in column:
                        header_l2 = combined_value
                    elif 'Column_Header_L3' in column:
                        header_l3 = combined_value
                    else:
                        metadata[column] = combined_value
                    break
        
        # Combine column headers
        header_parts = [h for h in [header_l1, header_l2, header_l3] if h]
        metadata['Column_Header'] = ' | '.join(header_parts) if header_parts else header_l2 or ''
        
        return metadata


def get_sheet_metadata_extractor() -> SheetMetadataExtractor:
    """Factory function for SheetMetadataExtractor."""
    return SheetMetadataExtractor()
