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
from typing import List, Dict, Any, Optional
from pathlib import Path
from collections import defaultdict

from src.utils import get_logger
from src.core import get_paths
from src.utils.date_utils import DateUtils
from src.utils.excel_utils import ExcelUtils

logger = get_logger(__name__)


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
        
        # Assign numeric sheet names (1, 2, 3...) like individual xlsx files
        sheet_number = 1
        for normalized_key in all_tables_by_full_title.keys():
            mapping = title_to_sheet_name.get(normalized_key, {})
            # Use simple numeric ID as sheet name
            mapping['unique_sheet_name'] = str(sheet_number)
            title_to_sheet_name[normalized_key] = mapping
            sheet_number += 1
        
        # Create consolidated output
        output_path = self.extracted_dir / output_filename
        
        try:
            with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
                # Create Master Index
                self._create_consolidated_index(writer, all_tables_by_full_title, title_to_sheet_name)
                
                # Create merged sheets
                for normalized_key, tables in all_tables_by_full_title.items():
                    mapping = title_to_sheet_name.get(normalized_key, {})
                    sheet_name = mapping.get('unique_sheet_name')
                    if sheet_name:
                        self._create_merged_table_sheet(writer, sheet_name, tables, transpose=transpose)
            
            # Add hyperlinks
            self._add_hyperlinks(output_path, all_tables_by_full_title, title_to_sheet_name)
            
            # Apply currency formatting to numeric cells
            self._apply_currency_format(output_path, all_tables_by_full_title, title_to_sheet_name)
            
            logger.info(f"Created consolidated report at {output_path}")
            logger.info(f"  - Tables merged: {len(all_tables_by_full_title)}")
            logger.info(f"  - Sources: {len(xlsx_files)}")
            
            return {
                'path': str(output_path),
                'tables_merged': len(all_tables_by_full_title),
                'sources_merged': len(xlsx_files),
                'sheet_names': [m.get('unique_sheet_name', '') for m in title_to_sheet_name.values()]
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
                metadata = {
                    'source': row.get('Source', Path(xlsx_path).stem),
                    'year': row.get('Year', ''),
                    'quarter': row.get('Quarter', ''),
                    'report_type': self._detect_report_type(str(row.get('Source', ''))),
                    'section': section,
                }
            else:
                section = ''
                metadata = {
                    'source': Path(xlsx_path).stem,
                    'year': '',
                    'quarter': '',
                    'report_type': '',
                    'section': '',
                }
            
            # Read table content (skip header rows)
            try:
                table_df = pd.read_excel(xlsx_path, sheet_name=sheet_name, header=None)
                
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
                
                # Compute row signature for strict matching
                raw_rows = table_df.iloc[:, 0].astype(str).tolist() if not table_df.empty else []
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
                    norm_rows.append(self._normalize_row_label(r_clean))
                
                row_sig = "|".join(norm_rows)
                
                # Create grouping key: Section + Title + Structure
                normalized_title = self._normalize_title_for_grouping(full_title)
                if section and section.strip():
                    normalized_key = f"{section.strip()}::{normalized_title}::{row_sig}"
                else:
                    normalized_key = f"Default::{normalized_title}::{row_sig}"
                
                all_tables_by_full_title[normalized_key].append({
                    'data': table_df,
                    'metadata': metadata,
                    'sheet_name': sheet_name,
                    'original_title': full_title,
                    'section': section,
                    'row_sig': row_sig
                })
                
                if normalized_key not in title_to_sheet_name:
                    clean_display = full_title.replace('→ ', '').strip() if full_title.startswith('→') else full_title
                    if section and section.strip():
                        display_with_section = f"{section.strip()} - {clean_display}"
                    else:
                        display_with_section = clean_display
                    
                    title_to_sheet_name[normalized_key] = {
                        'display_title': display_with_section,
                        'section': section.strip() if section else '',
                        'original_title': full_title,
                    }
                    
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
                
                # Build source reference: Q1,2025_page or FY2024_page
                year_val = str(int(meta['year'])) if isinstance(meta.get('year'), float) else str(meta.get('year', ''))
                quarter_val = str(meta.get('quarter', ''))
                page_val = str(meta.get('page', ''))
                
                if quarter_val and year_val:
                    ref = f"{quarter_val},{year_val}"
                elif year_val:
                    ref = f"FY{year_val}"
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
        # Sort by Section, then by Table Title
        df = df.sort_values(['Section', 'Table Title'])
        # Re-number after sorting and set Link to match #
        df['#'] = range(1, len(df) + 1)
        df['Link'] = df['#'].astype(str)
        
        # Update title_to_sheet_name with new numeric sheet names based on sorted order
        for idx, row in df.iterrows():
            normalized_key = row['_normalized_key']
            sheet_num = str(row['#'])
            if normalized_key in title_to_sheet_name:
                title_to_sheet_name[normalized_key]['unique_sheet_name'] = sheet_num
        
        # Drop the hidden column before saving
        df = df.drop(columns=['_normalized_key'])
        df.to_excel(writer, sheet_name='Index', index=False)
        
        # Auto-adjust column widths
        worksheet = writer.sheets['Index']
        for idx, col in enumerate(df.columns):
            col_letter = self._get_column_letter(idx)
            max_content_len = df[col].astype(str).map(len).max() if len(df) > 0 else 0
            header_len = len(col)
            max_len = max(max_content_len, header_len) + 2
            
            if col == '#':
                max_len = 5
            elif col == 'Section':
                max_len = min(max_len, 35)
            elif col == 'Table Title':
                max_len = min(max_len, 50)
            elif col == 'TableCount':
                max_len = 10
            elif col == 'Sources':
                max_len = min(max_len, 45)  # Wider for Q1,2025_p48 format
            elif col == 'Report Types':
                max_len = min(max_len, 15)
            elif col in ['Years', 'Quarters']:
                max_len = min(max_len, 20)
            elif col == 'Link':
                max_len = min(max_len, 32)
            else:
                max_len = min(max_len, 20)
            
            worksheet.column_dimensions[col_letter].width = max_len
    
    def _create_merged_table_sheet(
        self,
        writer: pd.ExcelWriter,
        title: str,
        tables: List[Dict[str, Any]],
        transpose: bool = False
    ) -> None:
        """Create merged sheet with tables from multiple sources."""
        if not tables:
            return
        
        all_columns = {}
        row_labels = []
        normalized_row_labels = {}
        
        for table_info in tables:
            df = table_info['data']
            meta = table_info['metadata']
            
            if df.empty or len(df.columns) < 2:
                continue
            
            # First column is row labels - filter out metadata rows
            for val in df.iloc[:, 0].tolist():
                if pd.notna(val):
                    val_str = str(val).strip()
                    # Skip metadata patterns
                    if val_str.startswith('Source:') or val_str.startswith('Page '):
                        continue
                    if val_str.startswith('$ in') or val_str.startswith('$,'):
                        continue
                    if val_str.startswith('← Back') or val_str == 'Row Label':
                        continue
                    if val_str.startswith('At ') and ('20' in val_str or 'March' in val_str or 'June' in val_str):
                        continue  # Skip date headers like "At March 31, 2025"
                    norm_val = self._normalize_row_label(val)
                    if norm_val and norm_val not in normalized_row_labels:
                        # Store original value for now - footnote cleaning happens at display time
                        normalized_row_labels[norm_val] = val_str
                        row_labels.append(val_str)
            
            # Extract column data with ORIGINAL headers from source
            # After slicing, the df structure is:
            #   Row 0: Source: ... (metadata)
            #   Row 1: Level 1 spanning headers (e.g., "", "", "", "", "%Change" or "Three Months Ended...")
            #   Row 2: Level 2 sub-headers (e.g., "$ in millions", "2024", "2023")
            #   Row 3+: Data rows
            
            for col_idx in range(1, len(df.columns)):
                # Get Level 1 header (from row 1 - spanning header row)
                # L1 headers are like "Three Months Ended...", "Six Months Ended..."
                # They span multiple columns, so we need to check if this column has a value
                level1_header = ''
                if len(df) > 1:
                    val = df.iloc[1, col_idx]
                    if pd.notna(val) and str(val).strip() and str(val).strip() != 'nan':
                        val_str = ExcelUtils.clean_year_string(val)
                        # L1 headers are descriptive text, not currency values
                        if not (val_str.startswith('$') and any(c.isdigit() for c in val_str)):
                            level1_header = val_str
                
                # Get Level 2 header (from row 2 - sub-header row with dates/years)
                # L2 headers are like "At December 31, 2024", "2024", "2023", "$ in millions"
                level2_header = ''
                if len(df) > 2:
                    val = df.iloc[2, col_idx]
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
                for row_label, value in zip(source_row_labels, col_values):
                    if pd.notna(row_label):
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
                
                # Check for duplicates
                is_duplicate = False
                col_data_str = str(sorted([(k, str(v).strip()) for k, v in row_data_map.items()]))
                
                for existing_key, existing_val in all_columns.items():
                    existing_data_str = str(sorted([(k, str(v).strip()) for k, v in existing_val.get('row_data_map', {}).items()]))
                    if col_data_str == existing_data_str:
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
            pd.DataFrame([{'← Back to Index': ''}]).to_excel(writer, sheet_name=title, index=False)
            return
        
        # Sort columns by date (DESCENDING - newest first)
        sorted_cols = sorted(
            all_columns.items(),
            key=lambda x: x[1]['sort_key'],
            reverse=True  # Newest first
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
            level1_headers.append(level1 if level1 else '')
            level2_headers.append(level2 if level2 else header)  # Fallback to combined header
            
            col_data = []
            for original_label in row_labels:
                norm_label = self._normalize_row_label(original_label)
                value = row_data_map.get(norm_label, '')
                # Clean currency values: '$1,234' -> 1234.0, keep 'N/A' and '-' as strings
                cleaned_value = self._clean_currency_value(value)
                # Also clean year floats (2024.0 -> '2024')
                if isinstance(cleaned_value, str):
                    cleaned_value = ExcelUtils.clean_cell_value(cleaned_value)
                col_data.append(cleaned_value)
            
            result_data[header] = col_data
        
        # Store header info for later cell merging
        self._last_level1_headers = level1_headers
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
        
        # Row 1: Row Header (Level 1) - section headers (rows where first cell has text, rest empty)
        row_l1_display = ', '.join(row_headers_l1[:5]) if row_headers_l1 else ''
        metadata_rows.append({first_col: f"Row Header (Level 1): {row_l1_display}"})
        
        # Row 2: Row Header (Level 2) - data row labels
        metadata_rows.append({first_col: f"Row Header (Level 2): {', '.join(row_headers_l2[:10])}"})
        
        # Row 3: Product/Entity (unique elements from L2 row headers)
        metadata_rows.append({first_col: f"Product/Entity: {', '.join(products)}"})
        
        # Row 4: Column Header (Level 1) - spanning headers like "Three Months Ended..."
        col_l1_str = ', '.join(col_headers_l1_display[:6]) if col_headers_l1_display else ''
        metadata_rows.append({first_col: f"Column Header (Level 1): {col_l1_str}"})
        
        # Row 5: Column Header (Level 2) - sub-headers like "December 31, 2024", "2024"
        col_l2_str = ', '.join(col_headers_l2_display[:10]) if col_headers_l2_display else ''
        metadata_rows.append({first_col: f"Column Header (Level 2): {col_l2_str}"})
        
        # Row 6: Year(s)
        if all_years:
            metadata_rows.append({first_col: f"Year(s): {', '.join(all_years)}"})
        else:
            metadata_rows.append({first_col: "Year(s):"})
        
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
        # Use centralized ExcelUtils.ensure_string_header
        
        # Create Level 1 header row (e.g., "Three Months Ended June 30,")
        level1_row = [ExcelUtils.ensure_string_header(h) for h in self._last_level1_headers]
        level1_df = pd.DataFrame([level1_row], columns=result_df.columns)
        
        # Create Level 2 header row (e.g., "2024", "2023", "% Change")
        level2_row = [ExcelUtils.ensure_string_header(h) for h in self._last_level2_headers]
        level2_df = pd.DataFrame([level2_row], columns=result_df.columns)
        
        # Concatenate: metadata + level1_header + level2_header + data
        final_df = pd.concat([metadata_df, level1_df, level2_df, result_df], ignore_index=True)
        
        # Write without pandas headers (we've included them in the data)
        final_df.to_excel(writer, sheet_name=title, index=False, header=False)
    
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
                
                # Fix both header rows - convert year floats to strings
                # Row 11: Level 1 headers (e.g., "Three Months Ended June 30,")
                # Row 12: Level 2 headers (e.g., "2024", "2023")
                # Use centralized ExcelUtils for year cleaning
                for header_row in [11, 12]:
                    for col in range(1, ws.max_column + 1):
                        cell = ws.cell(row=header_row, column=col)
                        if cell.value is not None:
                            # Use centralized utility for consistent year cleaning
                            cell.value = ExcelUtils.clean_year_string(cell.value)
                
                # Merge cells for spanning Level 1 headers
                # Detect consecutive columns with same Level 1 header value
                # Level 1 headers are in row 12, Level 2 in row 13
                col = 2  # Start from column B (column A is Row Label)
                while col <= ws.max_column:
                    cell_value = ws.cell(row=12, column=col).value
                    if cell_value and str(cell_value).strip():
                        # Find how many consecutive columns have same/empty value
                        span_end = col
                        for next_col in range(col + 1, ws.max_column + 1):
                            next_value = ws.cell(row=12, column=next_col).value
                            # Span if next cell is empty or has same value
                            if not next_value or str(next_value).strip() == '' or str(next_value).strip() == str(cell_value).strip():
                                span_end = next_col
                                # Clear the spanned cell (will be merged)
                                if next_value and str(next_value).strip() == str(cell_value).strip():
                                    ws.cell(row=12, column=next_col).value = ''
                            else:
                                break
                        
                        # Merge if span is more than 1 column
                        if span_end > col:
                            ws.merge_cells(start_row=12, start_column=col, end_row=12, end_column=span_end)
                            # Center the merged cell
                            from openpyxl.styles import Alignment
                            ws.cell(row=12, column=col).alignment = Alignment(horizontal='center')
                        
                        col = span_end + 1
                    else:
                        col += 1
                
                # Data starts at row 14 (after 10 metadata rows + 2 header rows = 12 rows, then row 13 is L2 header)
                # Column B onwards contains data (column A is row labels)
                for row in range(14, ws.max_row + 1):
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
