"""
Table Detection - Identify table boundaries and header rows.

Standalone module for detecting table structure in Excel data.
Used by: consolidated_exporter.py, table_merger.py
"""

import re
import pandas as pd
from typing import List, Tuple, Dict, Any

from src.utils.metadata_labels import MetadataLabels
from src.utils.financial_domain import DATE_HEADER_PATTERNS, is_year_value


# Valid year range for header detection
VALID_YEAR_RANGE = (2000, 2040)


class TableDetector:
    """
    Detect table boundaries, header rows, and structural patterns.
    
    Identifies:
    - Header row positions (L1, L2, L3)
    - Data start row
    - Embedded sub-table headers
    - Table structure patterns for merge grouping
    """
    
    @classmethod
    def is_embedded_header_row(cls, row_label: str, row_values: list) -> bool:
        """
        Detect if a row is an embedded sub-table header rather than a data row.
        
        Embedded headers look like:
        - "Three Months Ended June" | "Three Months Ended June 30," | "Six Months Ended..."
        - "2024" | "2023" | "2024" | "2023" (year row)
        - "At March 31, 2025" | "At December 31, 2024"
        
        Returns True if this row should be treated as a header, not data.
        """
        label_lower = str(row_label).strip().lower() if row_label else ''
        
        # Pattern 0: Metadata row patterns (these should ALWAYS be filtered)
        metadata_patterns = [
            'column header', 'row header', 'year/quarter', 'year(s):', 
            'table title:', 'source:', 'product/entity:'
        ]
        for pattern in metadata_patterns:
            if pattern in label_lower:
                return True
        
        # Pattern 1: Row label contains date period patterns
        for pattern in DATE_HEADER_PATTERNS:
            if pattern in label_lower:
                return True
        
        # Pattern 2: Row label is just a year (within valid range)
        if is_year_value(label_lower):
            return True
        
        # Pattern 3: All values in the row look like headers (dates, years, or empty)
        # This catches year rows like ["2024", "2023", "2024", "2023"]
        if row_values:
            non_empty_vals = [str(v).strip() for v in row_values if pd.notna(v) and str(v).strip()]
            if non_empty_vals:
                all_look_like_headers = all(
                    is_year_value(v) or  # Years
                    any(p in v.lower() for p in DATE_HEADER_PATTERNS) or  # Date text
                    v.lower() in ['nan', '']
                    for v in non_empty_vals
                )
                if all_look_like_headers:
                    return True
        
        return False
    
    @classmethod
    def find_header_rows(cls, df: pd.DataFrame, valid_year_range: Tuple[int, int] = VALID_YEAR_RANGE) -> Tuple[int, int, int]:
        """
        Dynamically find L1 header, L2 header, and data start row indices.
        
        Returns:
            (l1_row, l2_row, data_start_row) - Row indices in the DataFrame
        """
        l1_row = None
        l2_row = None
        data_start = None
        
        for i in range(len(df)):
            row = df.iloc[i]
            first_cell = str(row.iloc[0]).strip() if pd.notna(row.iloc[0]) else ''
            
            # Skip metadata rows - include ALL metadata prefixes
            metadata_prefixes = (
                MetadataLabels.SOURCES, '←', 
                MetadataLabels.CATEGORY_PARENT.rstrip(':'), MetadataLabels.LINE_ITEMS.rstrip(':'), 
                MetadataLabels.PRODUCT_ENTITY.rstrip(':'), MetadataLabels.COLUMN_HEADER_L2.rstrip(':'), 
                MetadataLabels.COLUMN_HEADER_L3.rstrip(':'), MetadataLabels.YEAR_QUARTER.rstrip(':'), 
                MetadataLabels.TABLE_TITLE.rstrip(':'), 'Column Header', 'None', 'Row Label'
            )
            if first_cell.startswith(metadata_prefixes) or first_cell == '':
                # Check if this is a header row (empty first cell but other cells have content)
                other_cells = [str(v).strip() for v in row.iloc[1:].tolist() if pd.notna(v) and str(v).strip()]
                if other_cells and first_cell == '':
                    # This looks like a spanning header row (L1)
                    if l1_row is None:
                        l1_row = i
                continue
            
            # Check if row is a unit/header indicator ($ in millions, $ in billions)
            if first_cell.lower().startswith('$ in'):
                if l2_row is None:
                    l2_row = i
                continue
            
            # Check if first cell is a year (L2 header)
            if first_cell.isdigit() and len(first_cell) == 4 and valid_year_range[0] <= int(first_cell) <= valid_year_range[1]:
                if l2_row is None:
                    l2_row = i
                continue
            
            # Check if this is a date period header pattern
            # IMPORTANT: Only treat as header if:
            #   1. First cell is short (< 30 chars) - long text is likely a row label
            #   2. First cell STARTS with the date pattern (not contains in middle)
            # This prevents "Average liquidity resources for three months ended" from being treated as a header
            if len(first_cell) < 30:
                # Check if first cell STARTS with date patterns (not contains)
                date_start_patterns = ['three months', 'six months', 'nine months', 'twelve months',
                                       'at march', 'at june', 'at september', 'at december',
                                       'at january', 'at february', 'at april', 'at may',
                                       'at july', 'at august', 'at october', 'at november']
                if any(first_cell.lower().startswith(p) for p in date_start_patterns):
                    if l1_row is None:
                        l1_row = i
                    continue
            
            # This looks like actual data
            if data_start is None and first_cell and first_cell not in ['Row Label', 'nan']:
                data_start = i
                break
        
        # Default fallbacks - be conservative about L2
        if l1_row is None:
            l1_row = 2  # Default: row after Source and blank
        
        # Only set l2_row if we actually found one - don't assume l1_row + 1 is L2
        # If l2_row is None, check if the row after L1 looks like a header row
        if l2_row is None and l1_row is not None and l1_row + 1 < len(df):
            next_row = df.iloc[l1_row + 1]
            first_cell = str(next_row.iloc[0]).strip() if pd.notna(next_row.iloc[0]) else ''
            
            # Check if this row looks like a L2 header (unit row or year row)
            is_l2_header = False
            if first_cell.lower().startswith('$ in'):
                is_l2_header = True
            elif first_cell.isdigit() and len(first_cell) == 4:
                is_l2_header = True
            elif first_cell == '':
                # Empty first cell with years in other cells
                other_cells = [str(v).strip() for v in next_row.iloc[1:].tolist() if pd.notna(v) and str(v).strip()]
                if other_cells and all(
                    (c.isdigit() and len(c) == 4 and valid_year_range[0] <= int(c) <= valid_year_range[1]) or
                    c.lower() in ['nan', '']
                    for c in other_cells
                ):
                    is_l2_header = True
            
            if is_l2_header:
                l2_row = l1_row + 1
        
        # Data starts after the last header row we found
        if data_start is None:
            if l2_row is not None:
                data_start = l2_row + 1
            elif l1_row is not None:
                data_start = l1_row + 1
            else:
                data_start = 3
        
        return (l1_row, l2_row, data_start)
    
    @classmethod
    def get_header_structure_pattern(cls, df: pd.DataFrame) -> str:
        """
        Detect the header structure pattern of a table for merge grouping.
        
        Tables only merge if they have the same header structure pattern AND
        compatible period type families.
        
        Returns pattern like:
            - "L3_ONLY::POINT_IN_TIME" - Point-in-time dates (e.g., "At December 2024")
            - "L2_L3::CUMULATIVE" - Period spanning (e.g., "Three Months Ended")
            - "L2_L3::ANNUAL" - Annual data (e.g., "Year Ended December 31")
            - "L1_L2_L3::CUMULATIVE" - Main header + period + years
        
        Period Type Families (merge within family, not across):
            CUMULATIVE: "Three Months Ended", "Six Months Ended", "Nine Months Ended"
            POINT_IN_TIME: "At March 31", "At June 30", "At September 30", "At December 31"
            ANNUAL: "Year Ended December 31"
            
        Example merges:
            QTD3 + QTD6 = YES (both CUMULATIVE)
            Q1 + Q2 = YES (both POINT_IN_TIME)
            Q1 + QTD3 = NO (different families)
        """
        if df.empty or len(df) < 2:
            return "UNKNOWN::UNKNOWN"
        
        has_l1 = False  # Main header (e.g., "Average Monthly Balance")
        has_l2 = False  # Period type (e.g., "Three Months Ended")
        has_l3 = False  # Years/dates (always present)
        
        # Track detected period type family
        period_family = "UNKNOWN"
        
        # Check first few rows for header patterns
        for i in range(min(5, len(df))):
            row = df.iloc[i]
            first_cell = str(row.iloc[0]).strip() if pd.notna(row.iloc[0]) else ''
            first_cell_lower = first_cell.lower()
            
            # Skip obvious metadata rows
            if first_cell.startswith(('Source', 'source', '←', 'Row Label', 'Category', 'Line Items')):
                continue
            
            # Collect non-empty values from data columns
            other_cells = [str(v).strip() for v in row.iloc[1:] if pd.notna(v) and str(v).strip()]
            
            if not other_cells:
                continue
            
            # Check if row has spanning header patterns (L1 or L2)
            sample_val = other_cells[0].lower() if other_cells else ''
            
            # CUMULATIVE family: Period types that accumulate
            cumulative_patterns = ['three months', 'six months', 'nine months', 
                                   'months ended', 'quarter ended']
            if any(p in sample_val for p in cumulative_patterns):
                has_l2 = True
                period_family = "CUMULATIVE"
                continue
            
            # ANNUAL family: Full year data
            annual_patterns = ['year ended', 'fiscal year', 'years ended']
            if any(p in sample_val for p in annual_patterns):
                has_l2 = True
                period_family = "ANNUAL"
                continue
            
            # L1 patterns: Main headers that describe content type
            l1_patterns = ['average monthly', 'balance', 'total assets', 'other assets']
            if any(p in sample_val for p in l1_patterns):
                has_l1 = True
                continue
            
            # POINT_IN_TIME family: Point-in-time dates
            point_in_time_patterns = ['at march', 'at june', 'at september', 'at december', 
                                      'as of', 'december 31', 'march 31', 'june 30', 'september 30']
            if any(p in sample_val for p in point_in_time_patterns):
                has_l3 = True
                if period_family == "UNKNOWN":
                    period_family = "POINT_IN_TIME"
                continue
            
            # Pure year values (e.g., "2024", "2023")
            if sample_val.isdigit() and len(sample_val) == 4:
                has_l3 = True
                continue
        
        # Build pattern string with period family
        if has_l1 and has_l2:
            base_pattern = "L1_L2_L3"
        elif has_l2:
            base_pattern = "L2_L3"
        else:
            base_pattern = "L3_ONLY"
            # If no L2, default to POINT_IN_TIME for L3_ONLY patterns
            if period_family == "UNKNOWN":
                period_family = "POINT_IN_TIME"
        
        return f"{base_pattern}::{period_family}"
    
    @classmethod
    def split_into_subtables(cls, df: pd.DataFrame, data_start_idx: int = 0) -> List[Tuple[pd.DataFrame, int]]:
        """
        Split a DataFrame at embedded header rows into separate sub-tables.
        
        Returns list of (sub_df, header_row_offset) tuples.
        Each sub-table starts at an embedded header row.
        """
        if df.empty or len(df) < 2:
            return [(df, data_start_idx)]
        
        subtables = []
        current_start = data_start_idx
        
        # Skip initial metadata/header rows (first 4 rows after data_start)
        # Look for embedded headers starting from row 4 onwards
        for i in range(data_start_idx + 4, len(df)):
            row = df.iloc[i]
            first_cell = str(row.iloc[0]).strip() if pd.notna(row.iloc[0]) else ''
            row_values = row.tolist()
            
            # Check if this row is an embedded header (new sub-table start)
            if cls.is_embedded_header_row(first_cell, row_values):
                # Save previous sub-table if it has data
                if i > current_start:
                    subtables.append((df.iloc[current_start:i].reset_index(drop=True), current_start))
                current_start = i
        
        # Add final sub-table
        if current_start < len(df):
            subtables.append((df.iloc[current_start:].reset_index(drop=True), current_start))
        
        return subtables if subtables else [(df, data_start_idx)]
