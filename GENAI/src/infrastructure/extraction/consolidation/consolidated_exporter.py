"""
Consolidated Excel Exporter.

Merges tables from multiple processed Excel files into a single consolidated report.
Tables are merged horizontally (same rows, columns for each period).

Features:
- Multi-file merge with row alignment
- Section + Title + Structure-based grouping
- Quarter format conversion (Q1, 2025)
- Date-sorted columns (newest first)
- Optional transpose (dates as rows)
"""

import glob
import re
import pandas as pd
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
from collections import defaultdict

from src.utils import get_logger
from src.core import get_paths
from src.utils.date_utils import DateUtils
from src.utils.excel_utils import ExcelUtils
from config.settings import settings

logger = get_logger(__name__)

# =============================================================================
# CONSTANTS (from settings for .env configurability)
# =============================================================================
VALID_YEAR_RANGE = (settings.EXTRACTION_YEAR_MIN, settings.EXTRACTION_YEAR_MAX)


class ConsolidatedExcelExporter:
    """
    Export consolidated tables from multiple quarterly/annual reports.
    
    Merges tables by Section + Title with horizontal column alignment.
    """
    
    def __init__(self):
        """Initialize exporter with paths from PathManager."""
        paths = get_paths()
        # Read from processed_advanced (after table merging) for correct pipeline flow:
        # extract -> process_advanced -> consolidate
        self.processed_dir = Path(paths.data_dir) / "processed_advanced" if hasattr(paths, 'data_dir') else Path("data/processed_advanced")
        self.extracted_dir = Path(paths.EXTRACTED_DIR) if hasattr(paths, 'EXTRACTED_DIR') else Path("data/extracted")
        
        # Ensure directories exist
        self.processed_dir.mkdir(parents=True, exist_ok=True)
        self.extracted_dir.mkdir(parents=True, exist_ok=True)
    
    def _parse_year_quarter_from_source(self, source: str) -> Tuple[str, str]:
        """
        Parse year and quarter from source filename pattern.
        
        Patterns:
        - 10k1224.pdf → 2024, Q4 (10-K filed Dec 2024)
        - 10q0325.pdf → 2025, Q1 (10-Q filed Mar 2025) 
        - 10q0624.pdf → 2024, Q2 (10-Q filed Jun 2024)
        
        Args:
            source: Source filename (e.g., '10k1224.pdf', '10q0325_tables')
            
        Returns:
            Tuple of (year, quarter) where quarter is 'Q4' for 10-K or 'Q1'-'Q4' for 10-Q
        """
        # Pattern: 10k MMYY or 10q MMYY
        match = re.search(r'(10[kq])(\d{2})(\d{2})', source.lower())
        if match:
            report_type = match.group(1)  # 10k or 10q
            month = int(match.group(2))
            year = 2000 + int(match.group(3))
            
            if report_type == '10k':
                return str(year), 'Q4'
            else:
                # Map month to quarter
                quarter_map = {3: 'Q1', 6: 'Q2', 9: 'Q3', 12: 'Q4', 1: 'Q4', 2: 'Q4'}
                # Handle edge cases: Jan/Feb filings are typically Q4 of previous year
                if month in [1, 2]:
                    year -= 1
                quarter = quarter_map.get(month, f'Q{(month-1)//3 + 1}')
                return str(year), quarter
        
        return '', ''
    
    def merge_processed_files(
        self,
        output_filename: str = "consolidated_tables.xlsx",
        transpose: bool = False
    ) -> dict:
        """
        Merge all processed xlsx files into a single consolidated report.
        
        Reads all *_tables.xlsx files from data/processed/, merges tables
        by title (row-aligned), and adds metadata columns.
        
        Args:
            output_filename: Output filename for consolidated report
            transpose: If True, dates become rows (time-series format)
            
        Returns:
            Dict with path, tables_merged, sources_merged, sheet_names
        """
        from openpyxl import load_workbook
        
        # Find all processed xlsx files
        pattern = str(self.processed_dir / "*_tables.xlsx")
        xlsx_files = glob.glob(pattern)
        
        # Filter out temp files (start with ~$)
        xlsx_files = [f for f in xlsx_files if not Path(f).name.startswith('~$')]
        
        if not xlsx_files:
            logger.warning(f"No processed xlsx files found in {self.processed_dir}")
            return {}
        
        logger.info(f"Found {len(xlsx_files)} processed files to merge")
        
        # Collect all tables from all files with metadata
        all_tables_by_full_title = defaultdict(list)
        title_to_sheet_name = {}
        
        for xlsx_path in xlsx_files:
            try:
                self._process_xlsx_file(
                    xlsx_path, 
                    all_tables_by_full_title, 
                    title_to_sheet_name
                )
            except Exception as e:
                logger.error(f"Error reading {xlsx_path}: {e}")
        
        if not all_tables_by_full_title:
            logger.warning("No tables collected for merging")
            return {}
        
        # PASS 1: Evaluate which tables have data (without creating sheets)
        # This prevents gaps in sheet numbering
        non_empty_tables = {}
        for normalized_key, tables in all_tables_by_full_title.items():
            if self._evaluate_table_has_data(tables, transpose=transpose):
                non_empty_tables[normalized_key] = tables
        
        logger.info(f"Found {len(non_empty_tables)} non-empty tables out of {len(all_tables_by_full_title)}")
        
        # Sort tables by page number for TOC-based ordering
        # Use minimum page number from any source, then section, then title
        def get_sort_key(k):
            mapping = title_to_sheet_name.get(k, {})
            min_page = mapping.get('min_page', 9999)
            return (
                min_page,
                mapping.get('section', ''),
                mapping.get('original_title', k)
            )
        
        sorted_keys = sorted(non_empty_tables.keys(), key=get_sort_key)
        
        # Assign sheet numbers ONLY to non-empty tables (no gaps)
        sheet_number = 1
        for normalized_key in sorted_keys:
            mapping = title_to_sheet_name.get(normalized_key, {})
            mapping['unique_sheet_name'] = str(sheet_number)
            title_to_sheet_name[normalized_key] = mapping
            sheet_number += 1
        
        # Create consolidated output
        output_path = self.extracted_dir / output_filename
        
        try:
            with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
                # PASS 2: Create sheets only for non-empty tables
                # Track which sheets are successfully created
                created_tables = {}
                for normalized_key in sorted_keys:
                    tables = non_empty_tables[normalized_key]
                    mapping = title_to_sheet_name.get(normalized_key, {})
                    sheet_name = mapping.get('unique_sheet_name')
                    if sheet_name:
                        sheet_created = self._create_merged_table_sheet(writer, sheet_name, tables, transpose=transpose)
                        if sheet_created:
                            created_tables[normalized_key] = tables
                        else:
                            logger.debug(f"Sheet {sheet_name} was not created (no data after processing)")
                
                # Create Index with ONLY successfully created sheets
                self._create_consolidated_index(writer, created_tables, title_to_sheet_name)
            
            # Add hyperlinks
            self._add_hyperlinks(output_path, created_tables, title_to_sheet_name)
            
            # Apply currency formatting to numeric cells
            self._apply_currency_format(output_path, created_tables, title_to_sheet_name)
            
            # Validate Index links match sheet names
            validation_result = self._validate_index_sheet_links(output_path)
            if not validation_result['valid']:
                logger.warning(f"Validation failed - missing sheets: {validation_result['missing_sheets']}")
            else:
                logger.info("Validation passed: all Index links have matching sheets")
            
            logger.info(f"Created consolidated report at {output_path}")
            logger.info(f"  - Tables merged: {len(created_tables)}")
            logger.info(f"  - Sources: {len(xlsx_files)}")
            
            return {
                'path': str(output_path),
                'tables_merged': len(created_tables),
                'sources_merged': len(xlsx_files),
                'sheet_names': [title_to_sheet_name[k].get('unique_sheet_name', '') for k in created_tables.keys()],
                'validation': validation_result
            }
            
        except Exception as e:
            logger.error(f"Failed to create consolidated report: {e}", exc_info=True)
            return {}

    
    def _process_xlsx_file(
        self,
        xlsx_path: str,
        all_tables_by_full_title: Dict[str, List],
        title_to_sheet_name: Dict[str, dict]
    ) -> None:
        """Process a single xlsx file and add tables to collection."""
        # Read Index sheet to get metadata
        index_df = pd.read_excel(xlsx_path, sheet_name='Index')
        
        # Get all sheet names except Index
        xl = pd.ExcelFile(xlsx_path)
        table_sheets = [s for s in xl.sheet_names if s != 'Index']
        
        # Create mapping from Link to full Table Title
        link_to_full_title = {}
        for _, idx_row in index_df.iterrows():
            full_title = str(idx_row.get('Table Title', ''))
            link = str(idx_row.get('Link', ''))
            if link.startswith('→ '):
                link = link[2:]
            if link and full_title:
                link_to_full_title[link] = full_title
        
        for sheet_name in table_sheets:
            full_title = link_to_full_title.get(sheet_name, sheet_name)
            
            # Find metadata for this sheet
            matching_rows = index_df[
                index_df['Table Title'].astype(str) == full_title
            ]
            
            if len(matching_rows) > 0:
                row = matching_rows.iloc[0]
                section = str(row.get('Section', '')) if 'Section' in row.index else ''
                source_name = str(row.get('Source', Path(xlsx_path).stem))
                
                # Get year/quarter from Index columns, or parse from filename
                year_val = row.get('Year', '')
                quarter_val = row.get('Quarter', '')
                
                # If year/quarter not in Index, parse from source filename
                if not year_val or str(year_val) in ['', 'nan', 'NaN']:
                    parsed_year, parsed_quarter = self._parse_year_quarter_from_source(source_name)
                    year_val = parsed_year
                    quarter_val = parsed_quarter
                
                metadata = {
                    'source': source_name,
                    'year': year_val,
                    'quarter': quarter_val,
                    'report_type': self._detect_report_type(source_name),
                    'section': section,
                    'page': row.get('PageNo', ''),
                }
            else:
                section = ''
                source_name = Path(xlsx_path).stem
                # Parse year/quarter from filename
                parsed_year, parsed_quarter = self._parse_year_quarter_from_source(source_name)
                
                metadata = {
                    'source': source_name,
                    'year': parsed_year,
                    'quarter': parsed_quarter,
                    'report_type': self._detect_report_type(source_name),
                    'section': '',
                    'page': '',
                }
            
            # Read table content (skip header rows)
            try:
                table_df = pd.read_excel(xlsx_path, sheet_name=sheet_name, header=None)
                
                # Extract Main Header (Level 0) from source metadata if present
                main_header = ''
                for idx in range(min(10, len(table_df))):  # Metadata is in first 10 rows
                    first_cell = str(table_df.iloc[idx, 0]) if pd.notna(table_df.iloc[idx, 0]) else ''
                    # Check for both old and new label names
                    if first_cell.startswith('Main Header:') or first_cell.startswith('Column Header (Level 0):'):
                        # Extract value after the colon
                        main_header = first_cell.split(':', 1)[1].strip() if ':' in first_cell else ''
                        break
                
                # Store main_header in metadata for consolidated output
                metadata['main_header'] = main_header
                
                # Dynamically find where data starts by looking for "Source:" row
                # Individual xlsx structure:
                #   Row 0: ← Back to Index
                #   Row 1-6: Metadata (Row Header, Column Header, etc.)
                #   Row 7: Year(s) or blank
                #   Row 8: Table Title
                #   Row 9: Blank
                #   Row 10+: "Source: ..." followed by actual table data
                data_start_row = 0
                for idx, row in table_df.iterrows():
                    first_cell = str(row.iloc[0]) if pd.notna(row.iloc[0]) else ''
                    if first_cell.startswith('Source:'):
                        data_start_row = idx
                        break
                
                # If Source: not found, fallback to row 10 or after metadata
                if data_start_row == 0:
                    # Look for first row that looks like table data
                    for idx, row in table_df.iterrows():
                        first_cell = str(row.iloc[0]) if pd.notna(row.iloc[0]) else ''
                        # Skip metadata patterns
                        if any(first_cell.startswith(p) for p in 
                               ['← Back', 'Row Header', 'Column Header', 'Product', 
                                'Table Title', 'Year(s)', 'Source:']):
                            continue
                        if first_cell.strip() == '':
                            continue
                        # This looks like data - start here
                        data_start_row = idx
                        break
                
                # Slice from data start
                if data_start_row > 0 and len(table_df) > data_start_row:
                    table_df = table_df.iloc[data_start_row:].reset_index(drop=True)
                
                # Split embedded sub-tables (e.g., "Investments" + "Income (loss)" in same table)
                subtables = self._split_into_subtables(table_df, 0)
                
                # Process each sub-table as a separate table entry
                for subtable_idx, (subtable_df, _) in enumerate(subtables):
                    if subtable_df.empty or len(subtable_df) < 2:
                        continue
                    
                    # Compute row signature for this sub-table
                    raw_rows = subtable_df.iloc[:, 0].astype(str).tolist() if not subtable_df.empty else []
                    norm_rows = []
                    for r in raw_rows:
                        r_clean = r.strip()
                        if not r_clean: 
                            continue
                        r_lower = r_clean.lower()
                        if r_lower == 'row label': 
                            continue
                        if r_lower.startswith('source:'): 
                            continue
                        if r_lower.startswith('page '): 
                            continue
                        if r_lower.startswith('$ in'): 
                            continue
                        # Skip metadata row patterns (these vary between files)
                        if r_lower.startswith('row header'):
                            continue
                        if r_lower.startswith('column header'):
                            continue
                        if r_lower.startswith('product/entity'):
                            continue
                        if r_lower.startswith('table title'):
                            continue
                        if r_lower.startswith('year(s)'):
                            continue
                        if r_lower.startswith('← back'):
                            continue
                        # Skip embedded header patterns
                        if self._is_embedded_header_row(r_clean, []):
                            continue
                        norm_rows.append(self._normalize_row_label(r_clean))
                    
                    row_sig = "|".join(norm_rows)
                    
                    # Skip if no valid rows found
                    if not row_sig:
                        continue
                    
                    # Create grouping key: Section + Title + [SubtableIdx] + Structure
                    normalized_title = self._normalize_title_for_grouping(full_title)
                    subtable_suffix = f"::sub{subtable_idx}" if len(subtables) > 1 else ""
                    
                    # Use full row signature to ensure exact structure matching
                    # Tables with any row differences will remain separate
                    row_sig_full = "|".join(norm_rows)
                    
                    if section and section.strip():
                        normalized_key = f"{section.strip()}::{normalized_title}{subtable_suffix}::{row_sig_full}"
                    else:
                        normalized_key = f"Default::{normalized_title}{subtable_suffix}::{row_sig_full}"
                    
                    all_tables_by_full_title[normalized_key].append({
                        'data': subtable_df,
                        'metadata': metadata,
                        'sheet_name': sheet_name,
                        'original_title': full_title if len(subtables) == 1 else f"{full_title} (Part {subtable_idx + 1})",
                        'section': section,
                        'row_sig': row_sig,
                        'subtable_idx': subtable_idx
                    })
                    
                    if normalized_key not in title_to_sheet_name:
                        clean_display = full_title.replace('→ ', '').strip() if full_title.startswith('→') else full_title
                        if len(subtables) > 1:
                            clean_display = f"{clean_display} (Part {subtable_idx + 1})"
                        if section and section.strip():
                            display_with_section = f"{section.strip()} - {clean_display}"
                        else:
                            display_with_section = clean_display
                        
                        # Parse page number for sorting (prefer 10-Q over 10-K for TOC order)
                        page_val = metadata.get('page', '')
                        report_type = metadata.get('report_type', '')
                        is_10q = '10-Q' in str(report_type).upper() or '10q' in str(metadata.get('source', '')).lower()
                        
                        try:
                            page_num = int(page_val) if page_val and str(page_val) != 'nan' else 9999
                        except (ValueError, TypeError):
                            page_num = 9999
                        
                        title_to_sheet_name[normalized_key] = {
                            'display_title': display_with_section,
                            'section': section.strip() if section else '',
                            'original_title': full_title,
                            'min_page': page_num,  # For TOC-based sorting
                            'has_10q_page': is_10q,  # Prefer 10-Q page numbers
                        }
                    else:
                        # Update min_page: prefer 10-Q pages over 10-K pages
                        page_val = metadata.get('page', '')
                        report_type = metadata.get('report_type', '')
                        is_10q = '10-Q' in str(report_type).upper() or '10q' in str(metadata.get('source', '')).lower()
                        
                        try:
                            page_num = int(page_val) if page_val and str(page_val) != 'nan' else 9999
                        except (ValueError, TypeError):
                            page_num = 9999
                        
                        existing_entry = title_to_sheet_name[normalized_key]
                        existing_has_10q = existing_entry.get('has_10q_page', False)
                        existing_min = existing_entry.get('min_page', 9999)
                        
                        # Priority: 10-Q page > 10-K page (regardless of page number)
                        if is_10q and not existing_has_10q:
                            # Replace with 10-Q page
                            existing_entry['min_page'] = page_num
                            existing_entry['has_10q_page'] = True
                        elif is_10q and existing_has_10q:
                            # Both are 10-Q, use min page
                            if page_num < existing_min:
                                existing_entry['min_page'] = page_num
                        elif not is_10q and not existing_has_10q:
                            # Both are 10-K, use min page
                            if page_num < existing_min:
                                existing_entry['min_page'] = page_num
                        # If existing is 10-Q and new is 10-K, keep existing
                    
            except Exception as e:
                logger.debug(f"Skipping sheet {sheet_name}: {e}")
    
    def _detect_report_type(self, source: str) -> str:
        """Detect report type from source filename. Delegates to ExcelUtils."""
        return ExcelUtils.detect_report_type(source)
    
    def _normalize_row_label(self, label: str) -> str:
        """Normalize row label for matching. Delegates to ExcelUtils."""
        return ExcelUtils.normalize_row_label(label)
    
    def _normalize_title_for_grouping(self, title: str) -> str:
        """Normalize title for grouping. Delegates to ExcelUtils."""
        return ExcelUtils.normalize_title_for_grouping(title)
    
    def _sanitize_sheet_name(self, name: str) -> str:
        """Sanitize for Excel sheet name. Delegates to ExcelUtils."""
        return ExcelUtils.sanitize_sheet_name(name)
    
    def _get_column_letter(self, idx: int) -> str:
        """Convert column index to letter. Delegates to ExcelUtils."""
        return ExcelUtils.get_column_letter(idx)
    
    def _clean_currency_value(self, val):
        """
        Convert currency string to float, keep special values as string.
        
        Delegates to ExcelUtils.clean_currency_value for centralized logic.
        """
        return ExcelUtils.clean_currency_value(val)
    
    def _evaluate_table_has_data(self, tables: List[Dict[str, Any]], transpose: bool = False) -> bool:
        """
        Evaluate if merged tables would have data (without creating a sheet).
        
        This mirrors the logic in _create_merged_table_sheet but only checks 
        if columns with data exist.
        
        Args:
            tables: List of table dictionaries to merge
            transpose: If True, check for transpose format
            
        Returns:
            True if merged table would have data, False otherwise
        """
        if not tables:
            return False
        
        all_columns = {}
        
        for table_info in tables:
            df = table_info['data']
            meta = table_info['metadata']
            
            if df.empty or len(df.columns) < 2:
                continue
            
            # Check for data columns (simplified version of _create_merged_table_sheet logic)
            l1_row, l2_row, data_start = self._find_header_rows(df)
            
            for col_idx in range(1, len(df.columns)):
                # Get column header
                header = ''
                if l2_row is not None and l2_row < len(df):
                    val = df.iloc[l2_row, col_idx]
                    if pd.notna(val) and str(val).strip() and str(val).strip() != 'nan':
                        header = ExcelUtils.clean_year_string(str(val))
                
                if not header:
                    header = f"Col_{col_idx}"
                
                # Check if column has actual data values
                col_values = df.iloc[:, col_idx].tolist()
                non_empty = [v for v in col_values if pd.notna(v) and str(v).strip() and str(v).strip() != 'nan']
                # Filter out header-like values
                non_empty = [x for x in non_empty if str(x).strip() != header]
                non_empty = [x for x in non_empty if not (
                    str(x).startswith('$') and 'in' in str(x).lower() or
                    str(x).isdigit() and len(str(x)) == 4 and 2000 <= int(str(x)) <= 2099
                )]
                
                if non_empty:
                    all_columns[header] = True
        
        return len(all_columns) > 0
    
    def _validate_index_sheet_links(self, output_path: Path) -> dict:
        """
        Verify all Index links have matching sheets.
        
        Args:
            output_path: Path to the consolidated xlsx file
            
        Returns:
            Dict with missing_sheets, orphan_sheets, and valid flag
        """
        try:
            from openpyxl import load_workbook
            
            wb = load_workbook(output_path)
            sheet_names = set(wb.sheetnames) - {'Index'}
            
            index_df = pd.read_excel(output_path, sheet_name='Index')
            
            # Extract link values (removing → prefix)
            link_values = set()
            for link in index_df['Link'].dropna().astype(str).tolist():
                clean_link = link.replace('→ ', '').strip()
                if clean_link:
                    link_values.add(clean_link)
            
            missing_sheets = link_values - sheet_names
            orphan_sheets = sheet_names - link_values
            
            return {
                'missing_sheets': missing_sheets,
                'orphan_sheets': orphan_sheets,
                'valid': len(missing_sheets) == 0,
                'total_links': len(link_values),
                'total_sheets': len(sheet_names)
            }
            
        except Exception as e:
            logger.error(f"Validation error: {e}")
            return {
                'missing_sheets': set(),
                'orphan_sheets': set(),
                'valid': False,
                'error': str(e)
            }

    
    def _is_embedded_header_row(self, row_label: str, row_values: list) -> bool:
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
        
        # Import domain patterns from centralized config
        from src.utils.domain_patterns import (
            DATE_HEADER_PATTERNS, VALID_YEAR_RANGE, is_year_value
        )
        
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
    
    def _split_into_subtables(self, df: pd.DataFrame, data_start_idx: int = 0) -> List[Tuple[pd.DataFrame, int]]:
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
            if self._is_embedded_header_row(first_cell, row_values):
                # Save previous sub-table if it has data
                if i > current_start:
                    subtables.append((df.iloc[current_start:i].reset_index(drop=True), current_start))
                current_start = i
        
        # Add final sub-table
        if current_start < len(df):
            subtables.append((df.iloc[current_start:].reset_index(drop=True), current_start))
        
        return subtables if subtables else [(df, data_start_idx)]
    
    def _find_header_rows(self, df: pd.DataFrame) -> Tuple[int, int, int]:
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
            
            # Skip metadata rows
            if first_cell.startswith('Source:') or first_cell == '' or first_cell.startswith('←'):
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
            if first_cell.isdigit() and len(first_cell) == 4 and VALID_YEAR_RANGE[0] <= int(first_cell) <= VALID_YEAR_RANGE[1]:
                if l2_row is None:
                    l2_row = i
                continue
            
            # Check if this is a date period header pattern
            if any(p in first_cell.lower() for p in ['months ended', 'at march', 'at june', 'at december']):
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
                    (c.isdigit() and len(c) == 4 and VALID_YEAR_RANGE[0] <= int(c) <= VALID_YEAR_RANGE[1]) or
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
    
    def _create_consolidated_index(
        self,
        writer: pd.ExcelWriter,
        tables_by_full_title: Dict[str, List[Dict[str, Any]]],
        title_to_sheet_name: Dict[str, dict]
    ) -> None:
        """Create master index for consolidated report."""
        index_data = []
        
        for normalized_key, tables in tables_by_full_title.items():
            sources = set()
            years = set()
            quarters = set()
            report_types = set()
            sections = set()
            source_refs = []  # List of "Q1,2025_page" references
            
            for t in tables:
                meta = t['metadata']
                section = t.get('section', '') or meta.get('section', '')
                if section and str(section).strip() and str(section).lower() != 'nan':
                    sections.add(str(section).strip())
                if meta.get('source'):
                    sources.add(str(meta['source']))
                if meta.get('year') and str(meta.get('year')) not in ['nan', 'NaN', '']:
                    years.add(str(int(meta['year'])) if isinstance(meta.get('year'), float) else str(meta.get('year')))
                if meta.get('quarter') and str(meta.get('quarter')) not in ['nan', 'NaN', '']:
                    quarters.add(str(meta['quarter']))
                if meta.get('report_type'):
                    report_types.add(str(meta['report_type']))
                
                # Build source reference: Q1,2025_page or Q4,2024_page
                year_val = str(int(meta['year'])) if isinstance(meta.get('year'), float) else str(meta.get('year', ''))
                quarter_val = str(meta.get('quarter', ''))
                page_val = str(meta.get('page', ''))
                
                if quarter_val and year_val:
                    ref = f"{quarter_val},{year_val}"
                elif year_val:
                    ref = f"Q4,{year_val}"
                else:
                    ref = str(meta.get('source', 'Unknown'))[:10]
                
                if page_val and page_val != 'nan':
                    ref += f"_p{page_val}"
                
                if ref and ref not in source_refs:
                    source_refs.append(ref)
            
            # Filter out NaN values
            quarters = {q for q in quarters if q and q.lower() != 'nan'}
            years = {y for y in years if y and y.lower() != 'nan'}
            sources = {s for s in sources if s and s.lower() != 'nan'}
            report_types = {r for r in report_types if r and r.lower() != 'nan'}
            sections = {s for s in sections if s and s.lower() != 'nan'}
            
            mapping = title_to_sheet_name.get(normalized_key, {})
            display_title = mapping.get('display_title', normalized_key)
            original_title = mapping.get('original_title', display_title)
            sheet_name = mapping.get('unique_sheet_name', self._sanitize_sheet_name(normalized_key))
            section_str = mapping.get('section', '') or ', '.join(sorted(sections))
            
            # Format source references (limit to 5 to avoid very long strings)
            source_refs_str = ', '.join(source_refs[:5])
            if len(source_refs) > 5:
                source_refs_str += f'... (+{len(source_refs) - 5})'
            
            index_data.append({
                '#': 0,  # Will be set after sorting
                'Section': section_str if section_str else '-',
                'Table Title': original_title if original_title else display_title,
                'TableCount': len(tables),
                'Sources': source_refs_str,
                'Report Types': ', '.join(sorted(report_types)),
                'Years': ', '.join(sorted(years, reverse=True)),
                'Quarters': ', '.join(sorted(quarters)),
                'Link': '',  # Will be set after sorting
                '_normalized_key': normalized_key  # Hidden key for sheet mapping
            })
        
        df = pd.DataFrame(index_data)
        # Keep the order from input (already sorted by page number in merge_processed_files)
        # Set # to row number for display (1-based)
        df['#'] = range(1, len(df) + 1)
        
        # Set Link to use the PRE-ASSIGNED sheet name from title_to_sheet_name
        # (NOT re-numbering based on sorted position)
        df['Link'] = df['_normalized_key'].map(
            lambda k: title_to_sheet_name.get(k, {}).get('unique_sheet_name', '')
        )
        
        # Drop the hidden column before saving
        df = df.drop(columns=['_normalized_key'])
        df.to_excel(writer, sheet_name='Index', index=False)

        
        # Auto-adjust column widths (using settings for configurability)
        worksheet = writer.sheets['Index']
        for idx, col in enumerate(df.columns):
            col_letter = self._get_column_letter(idx)
            max_content_len = df[col].astype(str).map(len).max() if len(df) > 0 else 0
            header_len = len(col)
            calculated_len = max(max_content_len, header_len) + 2
            
            # Use configured width from settings, or default
            configured_width = settings.INDEX_COLUMN_WIDTHS.get(
                col, settings.INDEX_COLUMN_WIDTHS.get('_default', 20)
            )
            max_len = min(calculated_len, configured_width) if col != '#' else configured_width
            
            worksheet.column_dimensions[col_letter].width = max_len
    
    def _create_merged_table_sheet(
        self,
        writer: pd.ExcelWriter,
        title: str,
        tables: List[Dict[str, Any]],
        transpose: bool = False
    ) -> bool:
        """Create merged sheet with tables from multiple sources.
        
        Returns:
            True if sheet has data, False if empty (sheet not created)
        """
        if not tables:
            return False
        
        all_columns = {}
        row_labels = []
        normalized_row_labels = {}
        
        for table_info in tables:
            df = table_info['data']
            meta = table_info['metadata']
            
            if df.empty or len(df.columns) < 2:
                continue
            
            # First column is row labels - filter out metadata rows and embedded headers
            for row_idx, val in enumerate(df.iloc[:, 0].tolist()):
                if pd.notna(val):
                    val_str = str(val).strip()
                    # Skip metadata patterns
                    if val_str.startswith('Source:') or val_str.startswith('Page '):
                        continue
                    if val_str.startswith('$ in') or val_str.startswith('$,'):
                        continue
                    if val_str.startswith('← Back') or val_str == 'Row Label':
                        continue
                    
                    # Skip embedded header rows (sub-table headers like "Three Months Ended")
                    row_values = df.iloc[row_idx].tolist() if row_idx < len(df) else []
                    if self._is_embedded_header_row(val_str, row_values):
                        continue
                    
                    norm_val = self._normalize_row_label(val)
                    if norm_val and norm_val not in normalized_row_labels:
                        # Store original value for now - footnote cleaning happens at display time
                        normalized_row_labels[norm_val] = val_str
                        row_labels.append(val_str)
            
            # Extract column data with ORIGINAL headers from source
            # Use dynamic header row detection instead of hardcoded indices
            l1_row, l2_row, data_start = self._find_header_rows(df)
            
            # Track spanning L1 headers for cell merging later
            current_l1_header = ''
            l1_header_spans = {}  # {header: [start_col, end_col]}
            
            for col_idx in range(1, len(df.columns)):
                # Get Level 1 header (spanning header row)
                level1_header = ''
                if l1_row is not None and l1_row < len(df):
                    val = df.iloc[l1_row, col_idx]
                    if pd.notna(val) and str(val).strip() and str(val).strip() != 'nan':
                        val_str = ExcelUtils.clean_year_string(val)
                        # L1 headers are descriptive text, not currency values
                        if not (val_str.startswith('$') and any(c.isdigit() for c in val_str)):
                            level1_header = val_str
                            current_l1_header = val_str
                            # Start tracking this spanning header
                            if val_str not in l1_header_spans:
                                l1_header_spans[val_str] = [col_idx, col_idx]
                    elif current_l1_header:
                        # Empty cell - extend the current spanning header
                        level1_header = current_l1_header
                        l1_header_spans[current_l1_header][1] = col_idx
                
                # Get Level 2 header (sub-header row with dates/years)
                level2_header = ''
                if l2_row is not None and l2_row < len(df):
                    val = df.iloc[l2_row, col_idx]
                    if pd.notna(val) and str(val).strip() and str(val).strip() != 'nan':
                        val_str = ExcelUtils.clean_year_string(val)
                        level2_header = val_str
                
                # Build the full header for display
                # Priority: If both exist, combine them. If only L2, use L2. 
                header_parts = []
                if level1_header and level1_header not in ['%', '%Change', 'nan', '$', '$ in millions']:
                    header_parts.append(level1_header)
                if level2_header and level2_header not in ['nan', '', '$ in millions']:
                    header_parts.append(level2_header)
                
                if header_parts:
                    header = ' '.join(header_parts)
                else:
                    header = f"Col_{col_idx}"
                
                # Final cleanup
                header = ExcelUtils.clean_year_string(header)
                
                sort_key = DateUtils.parse_date_from_header(header)
                norm_header = header.lower().strip()
                
                source_row_labels = df.iloc[:, 0].tolist()
                col_values = df.iloc[:, col_idx].tolist()
                
                row_data_map = {}
                for row_idx, (row_label, value) in enumerate(zip(source_row_labels, col_values)):
                    if pd.notna(row_label):
                        # Get full row values to detect embedded headers
                        row_values = df.iloc[row_idx].tolist() if row_idx < len(df) else []
                        
                        # Skip embedded header rows (sub-table headers like "Three Months Ended")
                        if self._is_embedded_header_row(row_label, row_values):
                            continue
                        
                        norm_row = self._normalize_row_label(row_label)
                        if norm_row:
                            row_data_map[norm_row] = value
                
                non_empty_data = [v for v in row_data_map.values() if pd.notna(v) and str(v).strip() and str(v).strip() != 'nan']
                non_empty_data = [x for x in non_empty_data if str(x).strip() != header]
                # Exclude header row values (units like "$ in billions", "$ in millions", years)
                # These are not actual data
                non_empty_data = [x for x in non_empty_data if not (
                    str(x).startswith('$') and 'in' in str(x).lower() or  # $ in millions/billions
                    str(x).isdigit() and len(str(x)) == 4 and 2000 <= int(str(x)) <= 2099  # Years like 2025
                )]
                
                if not non_empty_data:
                    continue
                
                # Check for duplicates - skip if SAME header AND same data already exists
                # This prevents multiple "At December 31, 2024" columns with identical data
                is_duplicate = False
                col_data_str = str(sorted([(k, str(v).strip()) for k, v in row_data_map.items()]))
                
                for existing_key, existing_val in all_columns.items():
                    existing_data_str = str(sorted([(k, str(v).strip()) for k, v in existing_val.get('row_data_map', {}).items()]))
                    existing_header = existing_val.get('header', '').lower().strip()
                    
                    # Duplicate if: same header OR same data
                    # This catches:
                    # 1. Same period from different sources with same data
                    # 2. Same data with slightly different header text
                    if col_data_str == existing_data_str:
                        is_duplicate = True
                        break
                    # Also check if header matches (same period, different data would still be kept)
                    if existing_header == norm_header and col_data_str == existing_data_str:
                        is_duplicate = True
                        break
                
                if not is_duplicate:
                    final_key = norm_header
                    counter = 1
                    while final_key in all_columns:
                        final_key = f"{norm_header}_{counter}"
                        counter += 1
                    
                    all_columns[final_key] = {
                        'header': header,
                        'level1_header': level1_header,  # For multi-level output
                        'level2_header': level2_header,  # For multi-level output
                        'row_data_map': row_data_map,
                        'sort_key': sort_key,
                        'source': meta.get('source', '')
                    }
        
        if not all_columns:
            # Don't create empty sheets - just return False
            return False
        
        # Sort columns by date (ASCENDING - chronological order: oldest first)
        # e.g., Dec 2024, Mar 2025, Jun 2025, Sep 2025
        sorted_cols = sorted(
            all_columns.items(),
            key=lambda x: x[1]['sort_key'],
            reverse=False  # Oldest first (chronological)
        )
        
        # Build result dataframe
        # Clean footnotes from row labels for final display
        display_row_labels = [ExcelUtils.clean_footnote_references(label) for label in row_labels]
        result_data = {'Row Label': display_row_labels}
        used_headers = {"row label"}
        
        # Track Level 1 and Level 2 headers separately for multi-level output
        level1_headers = ['']  # First column is Row Label (no L1 header)
        level2_headers = ['Row Label']  # Row Label is the L2 header for first column
        
        for _, col_info in sorted_cols:
            original_header = col_info['header']
            row_data_map = col_info.get('row_data_map', {})
            level1 = col_info.get('level1_header', '')
            level2 = col_info.get('level2_header', '')
            
            # Keep original header format (no conversion to Qn, YYYY)
            header = original_header
            
            counter = 1
            while header.lower() in used_headers:
                header = f"{original_header} ({counter})"
                counter += 1
            used_headers.add(header.lower())
            
            # Store Level 1 and Level 2 headers
            # If L1 is the same as L2 (both are just years), set L1 to empty to avoid duplication
            l1_val = ExcelUtils.ensure_string_header(level1) if level1 else ''
            l2_val = ExcelUtils.ensure_string_header(level2) if level2 else header
            
            # If L1 is just a year (same as L2), clear it to avoid duplicate headers
            if l1_val and l2_val and l1_val == l2_val:
                l1_val = ''
            # If L1 is a year and L2 is also a year, L1 should be empty
            if l1_val and l1_val.isdigit() and len(l1_val) == 4:
                l1_val = ''  # Years belong in L2 only
            
            level1_headers.append(l1_val)
            level2_headers.append(l2_val)
            
            col_data = []
            for original_label in row_labels:
                norm_label = self._normalize_row_label(original_label)
                value = row_data_map.get(norm_label, '')
                # Clean currency values: '$1,234' -> 1234.0, keep 'N/A' and '-' as strings
                cleaned_value = self._clean_currency_value(value)
                # Also clean year floats (2024.0 -> '2024')
                if isinstance(cleaned_value, str):
                    cleaned_value = ExcelUtils.clean_cell_value(cleaned_value)
                # Ensure numeric values are float (not int) for table data
                elif isinstance(cleaned_value, int):
                    cleaned_value = float(cleaned_value)
                col_data.append(cleaned_value)
            
            result_data[header] = col_data
        
        # Store header info for later cell merging
        # Deduplicate adjacent identical Level 1 headers (keep first, empty rest)
        # e.g., ["At Dec 31, 2024", "At Dec 31, 2024", "At Dec 31, 2024"] -> ["At Dec 31, 2024", "", ""]
        deduped_level1 = []
        prev_l1 = None
        for l1 in level1_headers:
            if l1 and l1 == prev_l1:
                deduped_level1.append('')  # Duplicate - empty it
            else:
                deduped_level1.append(l1)
                prev_l1 = l1 if l1 else prev_l1
        
        self._last_level1_headers = deduped_level1
        self._last_level2_headers = level2_headers
        
        result_df = pd.DataFrame(result_data)
        
        # Ensure column names are strings (prevent Excel from converting '2024' to 2024.0)
        # Use centralized ExcelUtils.ensure_string_header
        result_df.columns = [ExcelUtils.ensure_string_header(c) for c in result_df.columns]
        
        # Transpose if requested
        if transpose and len(result_df.columns) > 1:
            result_df = result_df.set_index('Row Label')
            result_df = result_df.T
            result_df.index.name = 'Period'
            result_df = result_df.reset_index()
            
            if 'Period' not in result_df.columns and len(result_df.columns) > 0:
                result_df = result_df.rename(columns={result_df.columns[0]: 'Period'})
        
        # Build metadata rows (matching individual file structure)
        # Collect metadata from all sources
        all_sources = sorted(set(t['metadata'].get('source', '') for t in tables if t['metadata'].get('source')))
        all_years = sorted(set(str(t['metadata'].get('year', '')) for t in tables if t['metadata'].get('year')), reverse=True)
        all_quarters = sorted(set(str(t['metadata'].get('quarter', '')) for t in tables if t['metadata'].get('quarter')))
        # Collect Main Headers from source tables (Level 0 spanning headers like "Average Monthly Balance")
        all_main_headers = sorted(set(
            str(t['metadata'].get('main_header', '')).strip() 
            for t in tables 
            if t['metadata'].get('main_header') and str(t['metadata'].get('main_header')).strip()
        ))
        original_title = tables[0].get('original_title', title) if tables else title
        section = tables[0].get('section', '') if tables else ''
        
        # Row Header Level 1: Section rows where first cell has text but rest is empty
        # These are rows like "Revenues" where only the first cell has content
        # Collect RAW values first, clean for display later
        row_headers_l1_raw = []
        for table_info in tables:
            df = table_info['data']
            if len(df) > 3:  # Skip if too few rows
                for idx in range(3, len(df)):  # Start after header rows
                    row = df.iloc[idx]
                    first_cell = str(row.iloc[0]).strip() if pd.notna(row.iloc[0]) else ''
                    # Check if rest of row is empty
                    rest_empty = all(pd.isna(v) or str(v).strip() == '' or str(v).strip() == 'nan' 
                                    for v in row.iloc[1:])
                    if first_cell and rest_empty and first_cell not in ['Row Label', 'nan']:
                        if first_cell not in row_headers_l1_raw:
                            row_headers_l1_raw.append(first_cell)
            break  # Only check first table since they should have same structure
        
        # Row Header Level 2: All data row labels (non-section rows) - keep raw for matching
        row_headers_l2_raw = []
        for label in row_labels:
            if label and not str(label).startswith('$'):
                label_str = str(label).strip()
                # Skip if it's a section header (in L1)
                if label_str not in row_headers_l1_raw and label_str not in row_headers_l2_raw:
                    row_headers_l2_raw.append(label_str)
        
        # NOW apply footnote cleaning ONLY for display purposes
        row_headers_l1 = [ExcelUtils.clean_footnote_references(h) for h in row_headers_l1_raw if h]
        row_headers_l2 = [ExcelUtils.clean_footnote_references(h) for h in row_headers_l2_raw if h]
        
        # Product/Entity: Unique entities from L2 row headers (deduplicated, first 5), cleaned for display
        products = row_headers_l2[:5]
        
        # Column Headers - from the stored level1_headers and level2_headers
        col_headers_l1_display = []  # Spanning headers like "Three Months Ended..."
        col_headers_l2_display = []  # Sub-headers like "December 31, 2024", "2024"
        
        if hasattr(self, '_last_level1_headers') and self._last_level1_headers:
            for h in self._last_level1_headers[1:]:  # Skip first (Row Label column)
                if h and str(h).strip() and str(h).strip() not in ['Row Label', '$ in millions']:
                    h_clean = str(h).strip()
                    if h_clean not in col_headers_l1_display:
                        col_headers_l1_display.append(h_clean)
        
        if hasattr(self, '_last_level2_headers') and self._last_level2_headers:
            for h in self._last_level2_headers[1:]:  # Skip first (Row Label column)
                if h and str(h).strip() and str(h).strip() not in ['Row Label', '$ in millions']:
                    h_clean = str(h).strip()
                    # Clean "At March 31, 2025" -> "March 31, 2025"
                    h_clean = re.sub(r'^At\s+', '', h_clean)
                    if h_clean not in col_headers_l2_display:
                        col_headers_l2_display.append(h_clean)
        
        # Create metadata section
        metadata_rows = []
        first_col = 'Row Label'
        
        # Row 0: Back link
        metadata_rows.append({first_col: '← Back to Index'})
        
        # Row 1: Category (Parent) - section headers (formerly Row Header Level 1)
        row_l1_display = ', '.join(row_headers_l1[:5]) if row_headers_l1 else ''
        metadata_rows.append({first_col: f"Category (Parent): {row_l1_display}"})
        
        # Row 2: Line Items - data row labels (formerly Row Header Level 2)
        metadata_rows.append({first_col: f"Line Items: {', '.join(row_headers_l2[:10])}"})
        
        # Row 3: Product/Entity (unique elements from L2 row headers)
        metadata_rows.append({first_col: f"Product/Entity: {', '.join(products)}"})
        
        # Row 4: Main Header - top-level spanning header (Level 0), only if present
        if all_main_headers:
            main_header_str = ', '.join(all_main_headers[:3])  # Limit to 3
            metadata_rows.append({first_col: f"Main Header: {main_header_str}"})
        
        # Row 5: Period Type - spanning headers (formerly Column Header Level 1)
        col_l1_str = ', '.join(col_headers_l1_display[:6]) if col_headers_l1_display else ''
        metadata_rows.append({first_col: f"Period Type: {col_l1_str}"})
        
        # Row 6: Year(s) - combined from column headers and metadata
        # Merge detected years from headers with years from source metadata
        combined_years = set()
        for h in col_headers_l2_display:
            # Extract years from header strings like "December 31, 2024"
            year_match = re.search(r'(20\d{2})', str(h))
            if year_match:
                combined_years.add(year_match.group(1))
        combined_years.update(all_years)
        years_str = ', '.join(sorted(combined_years, reverse=True)[:6]) if combined_years else ''
        metadata_rows.append({first_col: f"Year(s): {years_str}"})
        
        # Row 7: Blank
        metadata_rows.append({first_col: ''})
        
        # Row 8: Table Title
        display_title = f"{section} - {original_title}" if section else original_title
        metadata_rows.append({first_col: f"Table Title: {display_title}"})
        
        # Row 9: Sources
        metadata_rows.append({first_col: f"Sources: {', '.join(all_sources)}"})
        
        # Row 10: Blank
        metadata_rows.append({first_col: ''})
        
        # Create metadata DataFrame with same columns as result
        metadata_df = pd.DataFrame(metadata_rows)
        for col in result_df.columns:
            if col not in metadata_df.columns:
                metadata_df[col] = ''
        metadata_df = metadata_df[result_df.columns]
        
        # Add column header rows between metadata and data (multi-level headers)
        # Convert all header values to strings to prevent float display (e.g., 2025.0)
        
        def _convert_header_value(val):
            """Convert header value to clean string. Years stay as strings to prevent float conversion."""
            if val is None or val == '':
                return ''
            # Always use ensure_string_header which handles float→int→string conversion
            return ExcelUtils.ensure_string_header(val)
        
        # Create Level 1 header row (e.g., "Three Months Ended June 30,")
        level1_row = [_convert_header_value(h) for h in self._last_level1_headers]
        level1_df = pd.DataFrame([level1_row], columns=result_df.columns, dtype=str)
        
        # Create Level 2 header row (e.g., "2024", "2023", "% Change")
        # Use dtype=str to prevent Excel converting year strings to floats (2025.0)
        level2_row = [_convert_header_value(h) for h in self._last_level2_headers]
        level2_df = pd.DataFrame([level2_row], columns=result_df.columns, dtype=str)
        
        # Concatenate: metadata + level1_header + level2_header + data
        # Note: Data rows (result_df) keep their numeric types for currency values
        final_df = pd.concat([metadata_df, level1_df, level2_df, result_df], ignore_index=True)
        
        # Fix header rows: Convert any float years (e.g., 2025.0) back to strings
        # Header rows are 0-12 (metadata + L1 + L2), data starts at row 13
        header_row_count = len(metadata_df) + 2  # metadata + L1 + L2
        for row_idx in range(header_row_count):
            for col_idx in range(len(final_df.columns)):
                val = final_df.iloc[row_idx, col_idx]
                # Convert float years to integer strings (2025.0 -> "2025")
                if isinstance(val, float) and not pd.isna(val):
                    if val == int(val):  # It's a whole number
                        final_df.iloc[row_idx, col_idx] = str(int(val))
        
        # Write without pandas headers (we've included them in the data)
        final_df.to_excel(writer, sheet_name=title, index=False, header=False)
        return True  # Sheet has data
    
    def _add_hyperlinks(
        self,
        output_path: Path,
        all_tables_by_full_title: Dict[str, List],
        title_to_sheet_name: Dict[str, dict]
    ) -> None:
        """Add hyperlinks to consolidated workbook."""
        try:
            from openpyxl import load_workbook
            from openpyxl.styles import Font
            
            wb = load_workbook(output_path)
            
            # Add hyperlinks in Index sheet
            index_sheet = wb['Index']
            
            # Find Link column dynamically (same as individual xlsx logic)
            header_row = [index_sheet.cell(row=1, column=c).value for c in range(1, index_sheet.max_column + 1)]
            link_col = None
            for i, h in enumerate(header_row, start=1):
                if isinstance(h, str) and h.strip().lower() == 'link':
                    link_col = i
                    break
            
            if link_col is None:
                logger.warning("Link column not found in consolidated Index sheet")
            else:
                for row in range(2, index_sheet.max_row + 1):  # Skip header
                    cell = index_sheet.cell(row=row, column=link_col)
                    raw_value = cell.value
                    
                    # Extract sheet name (handle → prefix if present)
                    sheet_name = None
                    if raw_value is not None:
                        raw_str = str(raw_value).strip()
                        if raw_str.startswith('→'):
                            sheet_name = raw_str.lstrip('→').strip()
                        else:
                            sheet_name = raw_str
                    
                    if sheet_name and sheet_name in wb.sheetnames:
                        cell.hyperlink = f"#'{sheet_name}'!A1"
                        cell.value = f"→ {sheet_name}"
                        cell.font = Font(color="0000FF", underline="single")
                    elif sheet_name:
                        logger.debug(f"Sheet '{sheet_name}' not found in consolidated workbook")
            
            # Add back-links in each data sheet
            for sheet_name in wb.sheetnames:
                if sheet_name == 'Index':
                    continue
                ws = wb[sheet_name]
                cell = ws.cell(row=1, column=1)
                # Set back-link regardless of current value
                cell.value = "← Back to Index"
                cell.hyperlink = "#'Index'!A1"
                cell.font = Font(color="0000FF", underline="single")
            
            wb.save(output_path)
            logger.info(f"Added hyperlinks to consolidated workbook: {len(wb.sheetnames) - 1} sheets")
            
        except Exception as e:
            logger.warning(f"Could not add hyperlinks: {e}")
    
    def _apply_currency_format(
        self,
        output_path: Path,
        all_tables_by_full_title: Dict[str, List],
        title_to_sheet_name: Dict[str, dict]
    ) -> None:
        """Apply US currency number format to numeric data cells."""
        try:
            from openpyxl import load_workbook
            from openpyxl.styles.numbers import FORMAT_CURRENCY_USD_SIMPLE
            
            wb = load_workbook(output_path)
            
            # US currency format: $#,##0 (no decimals)
            CURRENCY_FORMAT = '$#,##0'
            
            for sheet_name in wb.sheetnames:
                if sheet_name == 'Index':
                    continue
                
                ws = wb[sheet_name]
                
                # Dynamically find header and data rows by looking for "Row Label" marker
                row_label_row = None
                for r in range(1, min(20, ws.max_row + 1)):
                    cell_val = ws.cell(row=r, column=1).value
                    if cell_val and str(cell_val).strip() == 'Row Label':
                        row_label_row = r
                        break
                
                if row_label_row is None:
                    row_label_row = 13  # Fallback to expected position
                
                # Header rows are 2 rows before Row Label row
                level1_header_row = row_label_row - 2
                level2_header_row = row_label_row - 1
                data_start_row = row_label_row + 1
                
                # Fix header rows - convert year floats to int (not float like 2024.0)
                for header_row in [level1_header_row, level2_header_row]:
                    if header_row > 0:
                        for col in range(1, ws.max_column + 1):
                            cell = ws.cell(row=header_row, column=col)
                            if cell.value is not None:
                                # Handle float years directly (e.g., 2024.0 -> 2024 int)
                                if isinstance(cell.value, float) and cell.value == int(cell.value):
                                    # Convert to int for years, keep as int for other whole numbers
                                    cell.value = int(cell.value)
                                elif isinstance(cell.value, str):
                                    # Clean string years (e.g., '2024.0' -> 2024 int)
                                    cleaned = ExcelUtils.clean_year_string(cell.value)
                                    if cleaned.isdigit() and len(cleaned) == 4:
                                        year = int(cleaned)
                                        if 2000 <= year <= 2099:
                                            cell.value = year
                
                # Merge cells for spanning Level 1 headers
                # Detect consecutive columns with same Level 1 header value
                col = 2  # Start from column B (column A is Row Label)
                while col <= ws.max_column:
                    cell_value = ws.cell(row=level1_header_row, column=col).value
                    if cell_value and str(cell_value).strip():
                        # Find how many consecutive columns have same/empty value
                        span_end = col
                        for next_col in range(col + 1, ws.max_column + 1):
                            next_value = ws.cell(row=level1_header_row, column=next_col).value
                            # Span if next cell is empty or has same value
                            if not next_value or str(next_value).strip() == '' or str(next_value).strip() == str(cell_value).strip():
                                span_end = next_col
                                # Clear the spanned cell (will be merged)
                                if next_value and str(next_value).strip() == str(cell_value).strip():
                                    ws.cell(row=level1_header_row, column=next_col).value = ''
                            else:
                                break
                        
                        # Merge if span is more than 1 column
                        if span_end > col:
                            ws.merge_cells(start_row=level1_header_row, start_column=col, end_row=level1_header_row, end_column=span_end)
                            # Center the merged cell
                            from openpyxl.styles import Alignment
                            ws.cell(row=level1_header_row, column=col).alignment = Alignment(horizontal='center')
                        
                        col = span_end + 1
                    else:
                        col += 1
                
                # Apply currency format to data cells
                for row in range(data_start_row, ws.max_row + 1):
                    for col in range(2, ws.max_column + 1):
                        cell = ws.cell(row=row, column=col)
                        # Apply currency format only to numeric cells
                        if isinstance(cell.value, (int, float)) and cell.value is not None:
                            cell.number_format = CURRENCY_FORMAT
            
            wb.save(output_path)
            logger.info(f"Applied currency formatting to consolidated workbook")
            
        except Exception as e:
            logger.warning(f"Could not apply currency formatting: {e}")


# =============================================================================
# SINGLETON PATTERN
# =============================================================================

_consolidated_exporter: Optional[ConsolidatedExcelExporter] = None


def get_consolidated_exporter() -> ConsolidatedExcelExporter:
    """
    Get or create global ConsolidatedExcelExporter instance.
    
    Returns:
        ConsolidatedExcelExporter singleton instance
    """
    global _consolidated_exporter
    
    if _consolidated_exporter is None:
        _consolidated_exporter = ConsolidatedExcelExporter()
    
    return _consolidated_exporter


def reset_consolidated_exporter() -> None:
    """Reset the exporter singleton (for testing)."""
    global _consolidated_exporter
    _consolidated_exporter = None
