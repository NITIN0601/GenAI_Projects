"""
Enhanced Index CSV Builder.

Merges original Index sheet with extracted metadata from all tables.
Handles multi-table sheets by exploding into multiple rows.
"""

from typing import Dict, List, Optional

import pandas as pd

from src.utils import get_logger
from .constants import MetadataColumnMapping
from .metadata_extractor import TableBlock

logger = get_logger(__name__)


class EnhancedIndexBuilder:
    """
    Builds enhanced Index CSV by merging original Index with table metadata.
    
    Features:
    - Preserves all original Index columns
    - Adds metadata columns extracted from table sheets
    - Explodes multi-table sheets into separate rows
    - Adds Table_Index and CSV_File columns
    """
    
    def __init__(self):
        self.logger = get_logger(f"{__name__}.{self.__class__.__name__}")
    
    def build_enhanced_index(
        self,
        original_index: pd.DataFrame,
        table_metadata: Dict[str, List[TableBlock]],
        csv_file_mapping: Dict[str, List[str]]
    ) -> pd.DataFrame:
        """
        Build enhanced Index by merging original Index with metadata.
        
        Handles the case where original Index already has multiple rows per sheet
        (different Location_IDs). If the number of tables matches the number of
        Index entries for a sheet, maps them 1:1. Otherwise, creates the cartesian
        product.
        
        Args:
            original_index: Original Index DataFrame from Excel
            table_metadata: Dict mapping sheet_id -> List[TableBlock]
            csv_file_mapping: Dict mapping sheet_id -> List[csv_filenames]
            
        Returns:
            Enhanced Index DataFrame with all metadata columns
        """
        enhanced_rows = []
        
        # First, group original Index rows by sheet_id (Table_ID)
        # This accounts for sheets with multiple Location_IDs
        if 'Table_ID' in original_index.columns:
            grouped = original_index.groupby('Table_ID')
        else:
            # Fallback to Link-based grouping
            grouped = original_index.groupby(
                original_index['Link'].apply(self._extract_sheet_id_from_link)
            )
        
        for sheet_id_key, group in grouped:
            sheet_id = str(sheet_id_key)
            
            # Get tables for this sheet
            tables = table_metadata.get(sheet_id, [])
            csv_files = csv_file_mapping.get(sheet_id, [])
            
            group_rows = list(group.iterrows())
            
            if not tables:
                # No tables found - create single row with empty metadata for each original row
                for _, row in group_rows:
                    enhanced_row = self._create_enhanced_row(
                        original_row=row,
                        table_block=None,
                        table_index=1,
                        csv_file=csv_files[0] if csv_files else ''
                    )
                    enhanced_rows.append(enhanced_row)
            elif len(tables) == len(group_rows):
                # 1:1 mapping - each original row maps to one table
                # This handles the case where Location_IDs correspond to sub-tables
                for i, (_, row) in enumerate(group_rows):
                    table = tables[i]
                    csv_file = csv_files[i] if i < len(csv_files) else ''
                    enhanced_row = self._create_enhanced_row(
                        original_row=row,
                        table_block=table,
                        table_index=table.table_index,
                        csv_file=csv_file
                    )
                    enhanced_rows.append(enhanced_row)
            else:
                # Mismatch - Use Greedy Best Match strategy
                # to avoid Cross Product (Cartesian Join) which causes duplicates.
                
                # Create a pool of available tables to match
                available_tables = list(tables)
                available_csvs = list(csv_files)
                
                # Keep track of which original rows have been assigned
                # We will process all original rows 
                
                for _, row in group_rows:
                    matched_table = None
                    matched_csv = ''
                    matched_idx = -1
                    
                    # Strategy 1: Title Match (if available)
                    row_title = str(row.get('Table Title', '')).strip().lower()
                    if row_title and available_tables:
                        for i, table in enumerate(available_tables):
                            # Check metadata title
                            meta_title = table.metadata.get('Table_Title_Metadata', '').strip().lower()
                            # Check for fuzzy match or containment
                            if row_title == meta_title or \
                               (len(row_title) > 5 and row_title in meta_title) or \
                               (len(meta_title) > 5 and meta_title in row_title):
                                matched_table = table
                                matched_csv = available_csvs[i] if i < len(available_csvs) else ''
                                matched_idx = i
                                break
                    
                    # Strategy 2: Order Match (Fallback)
                    if not matched_table and available_tables:
                        # Just take the first one available (preserving order)
                        matched_table = available_tables[0]
                        matched_csv = available_csvs[0] if available_csvs else ''
                        matched_idx = 0
                        
                    # Remove matched table from pool
                    if matched_table:
                        available_tables.pop(matched_idx)
                        if matched_idx < len(available_csvs):
                            available_csvs.pop(matched_idx)
                    
                    # Create row (populated or empty)
                    enhanced_row = self._create_enhanced_row(
                        original_row=row,
                        table_block=matched_table,
                        table_index=matched_table.table_index if matched_table else -1,
                        csv_file=matched_csv
                    )
                    enhanced_rows.append(enhanced_row)
                
                # Handle any remaining tables (orphan tables)
                # If we have extracted MORE tables than index rows, we need to preserve them
                # effectively creating new index entries for them.
                # Use the last row's generic info as a base? Or create blank?
                # Usually it's better to attribute to the sheet ID.
                if available_tables:
                    base_row = group_rows[-1][1] if group_rows else pd.Series()
                    for i, table in enumerate(available_tables):
                        csv_file = available_csvs[i] if i < len(available_csvs) else ''
                        enhanced_row = self._create_enhanced_row(
                            original_row=base_row,
                            table_block=table,
                            table_index=table.table_index,
                            csv_file=csv_file
                        )
                        enhanced_rows.append(enhanced_row)
        
        # Create DataFrame
        enhanced_df = pd.DataFrame(enhanced_rows)
        
        # Ensure correct column order
        columns = MetadataColumnMapping.ENHANCED_INDEX_COLUMNS
        for col in columns:
            if col not in enhanced_df.columns:
                enhanced_df[col] = ''
        
        # Reorder columns
        existing_cols = [c for c in columns if c in enhanced_df.columns]
        enhanced_df = enhanced_df[existing_cols]
        
        self.logger.info(
            f"Built enhanced index: {len(enhanced_df)} rows from "
            f"{len(original_index)} original rows"
        )
        
        return enhanced_df
    
    def _extract_sheet_id_from_link(self, link: str) -> str:
        """
        Extract sheet ID from link value.
        
        Examples:
            '→ 1' -> '1'
            '→ 23' -> '23'
            '1' -> '1'
        """
        if not link:
            return ''
        
        # Remove arrow prefix if present
        link = link.replace('→', '').strip()
        
        # Handle numeric sheet IDs
        if link.isdigit():
            return link
        
        return link
    
    def _create_enhanced_row(
        self,
        original_row: pd.Series,
        table_block: Optional[TableBlock],
        table_index: int,
        csv_file: str
    ) -> Dict:
        """Create enhanced row by merging original row with metadata."""
        # Start with original columns
        enhanced = {}
        for col in MetadataColumnMapping.INDEX_COLUMNS:
            enhanced[col] = original_row.get(col, '')
        
        # Add table index
        enhanced['Table_Index'] = table_index
        
        # Add metadata from table block
        if table_block:
            for col in MetadataColumnMapping.METADATA_COLUMNS:
                if col == 'Table_Index':
                    continue  # Already set
                if col == 'CSV_File':
                    enhanced[col] = csv_file
                else:
                    enhanced[col] = table_block.metadata.get(col, '')
        else:
            # No table block - empty metadata
            for col in MetadataColumnMapping.METADATA_COLUMNS:
                if col == 'Table_Index':
                    continue
                if col == 'CSV_File':
                    enhanced[col] = csv_file
                else:
                    enhanced[col] = ''
        
        return enhanced


def get_enhanced_index_builder() -> EnhancedIndexBuilder:
    """Factory function for EnhancedIndexBuilder."""
    return EnhancedIndexBuilder()
