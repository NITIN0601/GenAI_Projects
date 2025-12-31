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
from src.utils.metadata_labels import MetadataLabels, TableMetadata
from src.utils.metadata_builder import MetadataBuilder
from src.utils.financial_domain import (
    DATE_HEADER_PATTERNS,
    extract_quarter_from_header,
    extract_year_from_header,
    is_year_value,
)
from src.infrastructure.extraction.consolidation.consolidated_exporter_transpose import *
from src.infrastructure.extraction.exporters.base_exporter import BaseExcelExporter
# Import from new focused modules
from src.infrastructure.extraction.consolidation.table_detection import TableDetector
from src.infrastructure.extraction.consolidation.table_grouping import TableGrouper
from src.infrastructure.extraction.consolidation.excel_formatting import ExcelFormatter
from src.utils.constants import (
    CONSOLIDATION_YEAR_MIN,
    CONSOLIDATION_YEAR_MAX,
)
from config.settings import settings

logger = get_logger(__name__)

# =============================================================================
# CONSTANTS (from settings for .env configurability, with fallback to constants.py)
# =============================================================================
VALID_YEAR_RANGE = (
    getattr(settings, 'EXTRACTION_YEAR_MIN', CONSOLIDATION_YEAR_MIN), 
    getattr(settings, 'EXTRACTION_YEAR_MAX', CONSOLIDATION_YEAR_MAX)
)


class ConsolidatedExcelExporter(BaseExcelExporter):
    """
    Export consolidated tables from multiple quarterly/annual reports.
    
    Merges tables by Section + Title with horizontal column alignment.
    
    Inherits shared Excel utilities from BaseExcelExporter.
    """
    
    def __init__(self):
        """Initialize exporter with paths from PathManager."""
        super().__init__()
        paths = get_paths()
        # Step 4: reads from processed_advanced, outputs to consolidate/
        self.processed_dir = Path(paths.data_dir) / "processed_advanced" if hasattr(paths, 'data_dir') else Path("data/processed_advanced")
        self.consolidate_dir = Path(paths.data_dir) / "consolidate" if hasattr(paths, 'data_dir') else Path("data/consolidate")
        
        # Ensure directories exist
        self.processed_dir.mkdir(parents=True, exist_ok=True)
        self.consolidate_dir.mkdir(parents=True, exist_ok=True)

    
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
        
        Always generates BOTH:
        - Regular consolidated output (consolidated_tables.xlsx)
        - Transposed output (consolidated_tables_transposed.xlsx)
        
        Args:
            output_filename: Output filename for consolidated report
            transpose: If True, only generate transposed file (legacy, ignored)
            
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
        
        # Generate BOTH outputs: regular and transposed
        results = {}
        
        for is_transposed in [False, True]:
            # Determine output filename
            if is_transposed:
                base_name = Path(output_filename).stem
                ext = Path(output_filename).suffix or ".xlsx"
                current_output_filename = f"{base_name}_transposed{ext}"
                logger.info("Creating transposed consolidated report...")
            else:
                current_output_filename = output_filename
                logger.info("Creating regular consolidated report...")
            
            # PASS 1: Evaluate which tables have data (without creating sheets)
            non_empty_tables = {}
            for normalized_key, tables in all_tables_by_full_title.items():
                if self._evaluate_table_has_data(tables, transpose=is_transposed):
                    non_empty_tables[normalized_key] = tables
            
            logger.info(f"Found {len(non_empty_tables)} non-empty tables out of {len(all_tables_by_full_title)}")
            
            # Sort tables by page number for TOC-based ordering
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
            
            # Create output file
            output_path = self.consolidate_dir / current_output_filename

            
            try:
                with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
                    # PASS 2: Create sheets only for non-empty tables
                    created_tables = {}
                    for normalized_key in sorted_keys:
                        tables = non_empty_tables[normalized_key]
                        mapping = title_to_sheet_name.get(normalized_key, {})
                        sheet_name = mapping.get('unique_sheet_name')
                        if sheet_name:
                            sheet_created = self._create_merged_table_sheet(
                                writer, sheet_name, tables, transpose=is_transposed
                            )
                            if sheet_created:
                                created_tables[normalized_key] = tables
                            else:
                                logger.debug(f"Sheet {sheet_name} was not created (no data after processing)")
                    
                    # Create TOC_Sheet with hierarchical section columns
                    self._create_toc_sheet(writer, created_tables, title_to_sheet_name)
                    
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
                
                logger.info(f"Created {'transposed ' if is_transposed else ''}consolidated report at {output_path}")
                logger.info(f"  - Tables merged: {len(created_tables)}")
                logger.info(f"  - Sources: {len(xlsx_files)}")
                
                key = 'transposed' if is_transposed else 'regular'
                results[key] = {
                    'path': str(output_path),
                    'tables_merged': len(created_tables),
                    'sources_merged': len(xlsx_files),
                    'sheet_names': [title_to_sheet_name[k].get('unique_sheet_name', '') for k in created_tables.keys()],
                    'validation': validation_result
                }
                
            except Exception as e:
                logger.error(f"Failed to create {'transposed ' if is_transposed else ''}consolidated report: {e}", exc_info=True)
        
        # Return combined results (backward compat: use regular as main result)
        if 'regular' in results:
            result = results['regular'].copy()
            result['transposed_path'] = results.get('transposed', {}).get('path')
            return result
        return results.get('transposed', {})

    
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
                    # Check for both old and new label names using MetadataLabels
                    if first_cell.startswith(MetadataLabels.COLUMN_HEADER_L1) or first_cell.startswith('Main Header:') or first_cell.startswith('Column Header (Level 0):'):
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
                    if first_cell.startswith(MetadataLabels.SOURCES):
                        data_start_row = idx
                        break
                
                # If Source: not found, fallback to row 10 or after metadata
                if data_start_row == 0:
                    # Look for first row that looks like table data
                    for idx, row in table_df.iterrows():
                        first_cell = str(row.iloc[0]) if pd.notna(row.iloc[0]) else ''
                        # Skip metadata patterns
                        if any(first_cell.startswith(p) for p in 
                               [MetadataLabels.BACK_LINK, 'Row Header', 'Column Header', 'Product', 
                                MetadataLabels.TABLE_TITLE, MetadataLabels.COLUMN_HEADER_L3, MetadataLabels.SOURCES]):
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
                        if r_lower.startswith(MetadataLabels.SOURCES.lower()): 
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
                        if r_lower.startswith('year/quarter'):
                            continue
                        if r_lower.startswith('category'):
                            continue
                        if r_lower.startswith('line items'):
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
                    
                    # Normalize section field for grouping
                    # Fixes OCR broken words like 'Manageme nt' -> 'Management'
                    normalized_section = ""
                    if section and section.strip():
                        # Fix OCR broken words and normalize whitespace
                        fixed_section = ExcelUtils.fix_ocr_broken_words(section.strip())
                        normalized_section = re.sub(r'\s+', ' ', fixed_section).lower()
                    
                    # Extract BOTH Category AND Line Items for structure-based merging
                    # Tables with same structure should merge (even from different sources)
                    # Tables with different structure should NOT merge (even from same source/title)
                    
                    # 1. Extract Category (e.g., "Consolidated Results" vs "Ratios")
                    category_fingerprint = ""
                    for idx in range(min(10, len(subtable_df))):
                        first_cell = str(subtable_df.iloc[idx, 0]) if pd.notna(subtable_df.iloc[idx, 0]) else ''
                        if first_cell.startswith(MetadataLabels.CATEGORY_PARENT) or first_cell.startswith('Category'):
                            cat_value = first_cell.split(':', 1)[1].strip() if ':' in first_cell else ''
                            if cat_value:
                                cat_parts = [p.strip() for p in cat_value.split(',') if p.strip()]
                                if cat_parts:
                                    category_fingerprint = re.sub(r'[^a-z0-9]', '', cat_parts[0].lower())[:20]
                            break
                    
                    # 2. Extract Line Items fingerprint (e.g., "Net revenues, Earnings..." vs "Average liquidity, Loans...")
                    line_items_fingerprint = ""
                    for idx in range(min(10, len(subtable_df))):
                        first_cell = str(subtable_df.iloc[idx, 0]) if pd.notna(subtable_df.iloc[idx, 0]) else ''
                        if first_cell.startswith(MetadataLabels.LINE_ITEMS) or first_cell.startswith('Line Items:'):
                            li_value = first_cell.split(':', 1)[1].strip() if ':' in first_cell else ''
                            if li_value:
                                li_parts = [p.strip().lower() for p in li_value.split(',') if p.strip()]
                                # Skip common non-distinguishing items
                                li_parts = [p for p in li_parts if p not in ['$ in millions', 'in millions', 'except per share data']]
                                if li_parts:
                                    fingerprint_items = li_parts[:3]
                                    line_items_fingerprint = '|'.join(re.sub(r'[^a-z0-9]', '', item)[:15] for item in fingerprint_items)
                            break
                    
                    # Combined structure fingerprint: Category + Line Items
                    structure_fingerprint = f"{category_fingerprint}_{line_items_fingerprint}"
                    
                    # Extract header structure pattern for merge grouping
                    # Tables only merge if they have the same L1/L2/L3 structure
                    # This prevents merging L3_ONLY (point-in-time) with L2_L3 (period-based)
                    header_pattern = self._get_header_structure_pattern(subtable_df)
                    logger.debug(f"Table '{normalized_title}' has header pattern: {header_pattern}, structure: {structure_fingerprint}")
                    
                    # UPDATED: Grouping key uses 80% fuzzy matching on Section+Title
                    # Structure fingerprint and header_pattern must match exactly
                    # Section+Title can fuzzy match at 80% threshold
                    section_title_combo = f"{normalized_section}|{normalized_title}" if normalized_section else normalized_title
                    
                    # Exact key for structure+pattern (these must match exactly)
                    structure_key = f"{structure_fingerprint}::{header_pattern}"
                    
                    # Find best matching group using fuzzy Section+Title matching
                    best_match_key = self._find_fuzzy_matching_group(
                        all_tables_by_full_title,
                        section_title_combo,
                        structure_key,
                        threshold=0.80
                    )
                    
                    if best_match_key:
                        normalized_key = best_match_key
                    else:
                        # No fuzzy match found, create new key
                        normalized_key = f"{section_title_combo}::{structure_key}"
                    
                    # DEBUG: Log Reconciliations keys
                    if 'reconciliation' in normalized_title.lower():
                        logger.info(f"RECON KEY: sheet={sheet_name}, combo={section_title_combo[:40]}, struct={structure_key[:30]}, KEY={normalized_key[:80]}")

                    
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
    
    def _normalize_header_for_deduplication(self, header: str) -> str:
        """
        Normalize header for deduplication comparison.
        
        Delegates to TableGrouper for centralized logic.
        """
        return TableGrouper.normalize_header_for_deduplication(header)
    
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
                # Get column header - try multiple sources
                header = ''
                
                # Try L2 row first (usually years/dates)
                if l2_row is not None and l2_row < len(df):
                    val = df.iloc[l2_row, col_idx]
                    if pd.notna(val) and str(val).strip() and str(val).strip() != 'nan':
                        header = ExcelUtils.clean_year_string(str(val))
                
                # Fallback: Try L1 row (period descriptions like "Three Months Ended")
                if not header and l1_row is not None and l1_row < len(df):
                    val = df.iloc[l1_row, col_idx]
                    if pd.notna(val) and str(val).strip() and str(val).strip() != 'nan':
                        header = str(val).strip()
                
                # Last fallback: Use DataFrame column name if not generic
                if not header:
                    col_name = str(df.columns[col_idx])
                    if col_name and not col_name.startswith('Unnamed') and col_name != str(col_idx):
                        header = col_name
                
                # Final fallback: Col_N
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
        
        Delegates to TableDetector for centralized logic.
        """
        return TableDetector.is_embedded_header_row(row_label, row_values)
    
    def _find_fuzzy_matching_group(
        self,
        all_tables_by_full_title: Dict[str, List],
        section_title_combo: str,
        structure_key: str,
        threshold: float = 0.80
    ) -> Optional[str]:
        """
        Find an existing group key that fuzzy-matches the given Section+Title combo.
        
        Delegates to TableGrouper for centralized logic.
        """
        return TableGrouper.find_fuzzy_matching_group(
            all_tables_by_full_title, section_title_combo, structure_key, threshold
        )
    
    def _split_into_subtables(self, df: pd.DataFrame, data_start_idx: int = 0) -> List[Tuple[pd.DataFrame, int]]:
        """
        Split a DataFrame at embedded header rows into separate sub-tables.
        
        Delegates to TableDetector for centralized logic.
        """
        return TableDetector.split_into_subtables(df, data_start_idx)
    
    def _get_header_structure_pattern(self, df: pd.DataFrame) -> str:
        """
        Detect the header structure pattern of a table for merge grouping.
        
        Delegates to TableDetector for centralized logic.
        """
        return TableDetector.get_header_structure_pattern(df)
    
    def _find_header_rows(self, df: pd.DataFrame) -> Tuple[int, int, int]:
        """
        Dynamically find L1 header, L2 header, and data start row indices.
        
        Delegates to TableDetector for centralized logic.
        """
        return TableDetector.find_header_rows(df, VALID_YEAR_RANGE)
    
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
            
            # Fix OCR broken words and normalize whitespace in Section and Title
            section_clean = ExcelUtils.fix_ocr_broken_words(section_str) if section_str else ''
            section_clean = re.sub(r'\s+', ' ', section_clean).strip() if section_clean else '-'
            
            title_text = original_title if original_title else display_title
            title_clean = ExcelUtils.fix_ocr_broken_words(title_text) if title_text else ''
            title_clean = re.sub(r'\s+', ' ', title_clean).strip() if title_clean else ''
            
            index_data.append({
                '#': 0,  # Will be set after sorting
                'Section': section_clean,
                'Table Title': title_clean,
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
    
    def _create_toc_sheet(
        self,
        writer: pd.ExcelWriter,
        tables_by_full_title: Dict[str, List[Dict[str, Any]]],
        title_to_sheet_name: Dict[str, dict]
    ) -> None:
        """
        Create TOC sheet with hierarchical section columns.
        
        Columns: Table of Contents | Main Section | Section1 | Section2 | Section3 | Section4 | Table Title | Sheet | Sources
        
        Uses SectionHierarchyTracker for pattern-based classification.
        """
        from src.infrastructure.extraction.helpers.docling_helper import SectionHierarchyTracker
        
        # Initialize tracker with config-based patterns
        tracker = SectionHierarchyTracker()
        
        toc_data = []
        
        # First pass: collect all section names for pre-scan
        all_sections = []
        for normalized_key, tables in tables_by_full_title.items():
            mapping = title_to_sheet_name.get(normalized_key, {})
            section_str = mapping.get('section', '')
            
            if not section_str:
                for t in tables:
                    section = t.get('section', '') or t.get('metadata', {}).get('section', '')
                    if section and str(section).strip() and str(section).lower() != 'nan':
                        section_str = str(section).strip()
                        break
            
            if section_str:
                all_sections.append((1, section_str))  # Page 1 as placeholder
        
        # Pre-scan to identify repeating headers
        tracker.pre_scan_headers(all_sections)
        
        # Second pass: process each table group
        for normalized_key, tables in tables_by_full_title.items():
            mapping = title_to_sheet_name.get(normalized_key, {})
            display_title = mapping.get('display_title', normalized_key)
            original_title = mapping.get('original_title', display_title)
            sheet_name = mapping.get('unique_sheet_name', str(len(toc_data) + 1))
            section_str = mapping.get('section', '')
            
            # Extract section from tables if not in mapping
            if not section_str:
                for t in tables:
                    section = t.get('section', '') or t.get('metadata', {}).get('section', '')
                    if section and str(section).strip() and str(section).lower() != 'nan':
                        section_str = str(section).strip()
                        break
            
            # Use tracker to classify section
            if section_str:
                hierarchy = tracker.process_header(section_str.strip(), 1)
            else:
                hierarchy = tracker.get_current_hierarchy()
            
            # Get clean title
            title_text = original_title if original_title else display_title
            title_clean = ExcelUtils.fix_ocr_broken_words(str(title_text)) if title_text else ''
            title_clean = re.sub(r'\s+', ' ', title_clean).strip()
            title_clean = re.sub(r'^Table Title:\s*', '', title_clean, flags=re.IGNORECASE)
            
            # Get sources
            source_refs = []
            for t in tables:
                meta = t.get('metadata', {})
                year_val = str(int(meta['year'])) if isinstance(meta.get('year'), float) else str(meta.get('year', ''))
                quarter_val = str(meta.get('quarter', ''))
                page_val = str(meta.get('page', ''))
                
                if quarter_val and year_val:
                    ref = f"{quarter_val},{year_val}"
                elif year_val:
                    ref = f"Q4,{year_val}"
                else:
                    ref = str(meta.get('source', ''))[:10]
                
                if page_val and page_val != 'nan':
                    ref += f"_p{page_val}"
                
                if ref and ref not in source_refs:
                    source_refs.append(ref)
            
            sources_str = ', '.join(source_refs[:3])
            if len(source_refs) > 3:
                sources_str += '...'
            
            toc_data.append({
                'Table of Contents': hierarchy.get('toc', '') or '-',
                'Main Section': hierarchy.get('main', '') or '-',
                'Section1': hierarchy.get('section1', '') or '-',
                'Section2': hierarchy.get('section2', '') or '-',
                'Section3': hierarchy.get('section3', '') or '-',
                'Section4': hierarchy.get('section4', '') or '-',
                'Table Title': title_clean,
                'Sheet': sheet_name,
                'Sources': sources_str
            })
        
        # Create DataFrame and write to sheet
        df = pd.DataFrame(toc_data)
        
        # Sort by hierarchy
        df = df.sort_values(
            by=['Table of Contents', 'Main Section', 'Section1', 'Section2', 'Section3', 'Section4', 'Table Title'],
            key=lambda x: x.astype(str).str.lower().fillna('')
        )
        
        df.to_excel(writer, sheet_name='TOC', index=False)
        
        # Auto-adjust column widths
        worksheet = writer.sheets['TOC']
        for idx, col in enumerate(df.columns):
            col_letter = self._get_column_letter(idx)
            max_content_len = df[col].astype(str).map(len).max() if len(df) > 0 else 0
            header_len = len(col)
            calculated_len = max(max_content_len, header_len) + 2
            max_len = min(calculated_len, 50)
            worksheet.column_dimensions[col_letter].width = max_len
        
        logger.info(f"Created TOC sheet with {len(df)} entries")
    
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
        # Track section headers for disambiguation of duplicate row labels
        # (e.g., "Institutional Securities" appears under multiple sections)
        label_to_section = {}  # Maps normalized label to its section
        
        for table_info in tables:
            df = table_info['data']
            meta = table_info['metadata']
            
            if df.empty or len(df.columns) < 2:
                continue
            
            # First, find the "Row Label" header row to know where data starts
            # This ensures we only collect actual data row labels, not headers
            row_label_row_idx = None
            for idx, val in enumerate(df.iloc[:, 0].tolist()):
                if pd.notna(val) and str(val).strip() == 'Row Label':
                    row_label_row_idx = idx
                    break
            
            # If "Row Label" not found, find data start dynamically
            if row_label_row_idx is None:
                # Look for Source(s) row, then skip to first data row
                source_row_idx = None
                unit_row_idx = None
                first_data_row_idx = None
                
                for idx, val in enumerate(df.iloc[:, 0].tolist()):
                    val_str = str(val).strip() if pd.notna(val) else ''
                    val_lower = val_str.lower()
                    
                    # Find Source(s) row
                    if val_str.startswith(MetadataLabels.SOURCES):
                        source_row_idx = idx
                    # Find unit header row ($ in millions, etc.)
                    elif val_lower.startswith('$ in'):
                        unit_row_idx = idx
                    # First non-metadata row after Source(s) is the data start
                    elif source_row_idx is not None and val_str:
                        # Skip blank rows and metadata patterns
                        if not val_str.startswith(('←', 'Category', 'Line Items', 'Product', 'Column Header', 'Year', 'Table Title')):
                            if not val_lower.startswith('$ in'):
                                first_data_row_idx = idx
                                break
                
                # Determine data_start_for_labels
                if first_data_row_idx is not None:
                    # We found the first data row - use its index directly
                    data_start_for_labels = first_data_row_idx
                elif unit_row_idx is not None:
                    # Data starts after unit row
                    data_start_for_labels = unit_row_idx + 1
                else:
                    # Fallback to _find_header_rows
                    _, _, data_start_fallback = self._find_header_rows(df)
                    data_start_for_labels = data_start_fallback
            else:
                # Data rows start AFTER the "Row Label" row
                data_start_for_labels = row_label_row_idx + 1
            
            # First pass: identify section headers (rows with label but no data)
            current_section = ''
            
            # Collect row labels starting from data_start_for_labels
            for row_idx in range(data_start_for_labels, len(df)):
                val = df.iloc[row_idx, 0]
                if pd.notna(val):
                    val_str = str(val).strip()
                    # Skip metadata patterns that might appear in data
                    if val_str.startswith((MetadataLabels.SOURCES, 'Page ')):
                        continue
                    if val_str.startswith('$ in') or val_str.startswith('$,'):
                        continue
                    if val_str.startswith('← Back') or val_str == 'Row Label':
                        continue
                    if val_str.startswith(('Category', 'Line Items', 'Product', 'Period', 'Year', 'Table Title', 'Column Header')):
                        continue
                    
                    # Skip embedded header rows (sub-table headers like "Three Months Ended")
                    row_values = df.iloc[row_idx].tolist() if row_idx < len(df) else []
                    if self._is_embedded_header_row(val_str, row_values):
                        continue
                    
                    # Check if this is a section header (has label but no data values)
                    has_data = any(pd.notna(row_values[i]) and str(row_values[i]).strip() 
                                   and str(row_values[i]).strip() != 'nan'
                                   for i in range(1, len(row_values)))
                    
                    if not has_data:
                        # This is a section header - update current section and add to row_labels
                        current_section = val_str
                        norm_val = self._normalize_row_label(val)
                        if norm_val and norm_val not in normalized_row_labels:
                            normalized_row_labels[norm_val] = val_str
                            # Store the key (norm_val) in row_labels, not the display label
                            row_labels.append(norm_val)
                            label_to_section[norm_val] = ''  # Section headers have no parent section
                    else:
                        # This is a data row - use section prefix for unique matching
                        norm_val = self._normalize_row_label(val)
                        # Create a section-prefixed key for disambiguation
                        section_key = f"{current_section}::{norm_val}" if current_section else norm_val
                        
                        if section_key not in normalized_row_labels:
                            normalized_row_labels[section_key] = val_str
                            # Store the section_key in row_labels for unique identification
                            row_labels.append(section_key)
                            label_to_section[section_key] = current_section
            
            # Extract column data with ORIGINAL headers from source
            # Use the same data_start we found for row labels to ensure consistency
            l1_row, l2_row, _ = self._find_header_rows(df)
            # Use data_start_for_labels to sync with row label collection
            data_start = data_start_for_labels
            
            # Get Level 0 header (Main Header) from table metadata
            # This comes from the source file's "Main Header:" row
            level0_header_from_meta = meta.get('main_header', '')
            
            # Track spanning L1 headers for cell merging later
            current_l1_header = ''
            l1_header_spans = {}  # {header: [start_col, end_col]}
            
            # Track current section for this specific table's data extraction
            current_section_for_data = ''
            
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
                    # Fallback 1: Use DataFrame column name if not generic
                    col_name = str(df.columns[col_idx])
                    if col_name and not col_name.startswith('Unnamed') and col_name != str(col_idx):
                        header = col_name
                    else:
                        # Fallback 2: Use column index as header (will be deduplicated later)
                        header = f"Column {col_idx}"
                
                # Final cleanup
                header = ExcelUtils.clean_year_string(header)
                
                sort_key = DateUtils.parse_date_from_header(header)
                
                # Normalize header for deduplication comparison
                # This handles case, month abbreviations, punctuation, and decimal years
                norm_header = self._normalize_header_for_deduplication(header)
                
                # Get row labels and values starting from data_start (not from row 0!)
                # This prevents header row values from being extracted as data
                source_row_labels = df.iloc[data_start:, 0].tolist()
                col_values = df.iloc[data_start:, col_idx].tolist()
                
                row_data_map = {}
                current_section_for_data = ''  # Track current section during data extraction
                
                for rel_idx, (row_label, value) in enumerate(zip(source_row_labels, col_values)):
                    row_idx = data_start + rel_idx  # Actual row index in DataFrame
                    if pd.notna(row_label):
                        row_label_str = str(row_label).strip()
                        
                        # Get full row values to detect embedded headers
                        row_values = df.iloc[row_idx].tolist() if row_idx < len(df) else []
                        
                        # Skip embedded header rows (sub-table headers like "Three Months Ended")
                        if self._is_embedded_header_row(row_label, row_values):
                            continue
                        
                        # Check if this row has data values (non-empty cells after the label)
                        has_data = any(pd.notna(row_values[i]) and str(row_values[i]).strip() 
                                       and str(row_values[i]).strip() != 'nan'
                                       for i in range(1, len(row_values)))
                        
                        norm_row = self._normalize_row_label(row_label)
                        
                        if not has_data:
                            # This is a section header - update current section
                            current_section_for_data = row_label_str
                            if norm_row:
                                row_data_map[norm_row] = value  # Section headers stay as simple keys
                        else:
                            # This is a data row - use section prefix for matching
                            if norm_row:
                                section_key = f"{current_section_for_data}::{norm_row}" if current_section_for_data else norm_row
                                row_data_map[section_key] = value
                
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
                    
                    # FIXED: Only mark as duplicate if BOTH header AND data match
                    # This prevents dropping valid columns that happen to have same data but different periods
                    # Changed from OR to AND
                    if existing_header == norm_header and col_data_str == existing_data_str:
                        is_duplicate = True
                        logger.debug(f"Removing exact duplicate column: '{header}' (same as '{existing_val.get('header')}')")
                        break
                
                if not is_duplicate:
                    final_key = norm_header
                    counter = 1
                    while final_key in all_columns:
                        final_key = f"{norm_header}_{counter}"
                        counter += 1
                    
                    all_columns[final_key] = {
                        'header': header,
                        'level0_header': level0_header_from_meta,  # Main Header (e.g., 'Average Monthly Balance')
                        'level1_header': level1_header,  # Period Type (e.g., 'Three Months Ended')
                        'level2_header': level2_header,  # Years/Dates (e.g., '2024')
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
        # row_labels now contains section_keys, convert back to display labels
        display_row_labels = [
            ExcelUtils.clean_footnote_references(normalized_row_labels.get(key, key)) 
            for key in row_labels
        ]
        result_data = {'Row Label': display_row_labels}
        used_headers = {"row label"}
        
        # Track Level 0, Level 1 and Level 2 headers separately for multi-level output
        # Naming: L0 = "Column Header L1", L1 = "Column Header L2", L2 = "Column Header L3"
        level0_headers = ['']  # First column is Row Label (no L0 header)
        level1_headers = ['']  # First column is Row Label (no L1 header)
        level2_headers = ['Row Label']  # Row Label is the L2/L3 header for first column
        
        for _, col_info in sorted_cols:
            original_header = col_info['header']
            row_data_map = col_info.get('row_data_map', {})
            level0 = col_info.get('level0_header', '')
            level1 = col_info.get('level1_header', '')
            level2 = col_info.get('level2_header', '')
            source = col_info.get('source', '')
            
            # Keep original header format (no conversion to Qn, YYYY)
            header = original_header
            
            counter = 1
            while header.lower() in used_headers:
                header = f"{original_header} ({counter})"
                counter += 1
            used_headers.add(header.lower())
            
            # Store Level 0 header (Main Header like "Average Monthly Balance")
            l0_val = ExcelUtils.ensure_string_header(level0) if level0 else ''
            
            # Store Level 1 and Level 2 headers
            # If L1 is the same as L2 (both are just years), set L1 to empty to avoid duplication
            l1_val = ExcelUtils.ensure_string_header(level1) if level1 else ''
            l2_val = ExcelUtils.ensure_string_header(level2) if level2 else header
            
            # 10-K Special Case: If L2 is just a year and source is 10-K, prefix with "YTD, "
            # e.g., "2024" -> "YTD, 2024"
            is_10k = '10k' in source.lower() if source else False
            if l2_val and l2_val.isdigit() and len(l2_val) == 4 and is_10k:
                if not l1_val:  # Only add YTD if L1 is empty (no period type specified)
                    l2_val = f"YTD, {l2_val}"
            
            # If L1 is just a year (same as L2), clear it to avoid duplicate headers
            if l1_val and l2_val and l1_val == l2_val:
                l1_val = ''
            # If L1 is a year and L2 is also a year, L1 should be empty
            if l1_val and l1_val.replace(',', '').strip().isdigit():
                # Check if it looks like just a year (4 digits)
                clean_l1 = l1_val.replace(',', '').strip()
                if len(clean_l1) == 4 and clean_l1.isdigit():
                    l1_val = ''  # Years belong in L2 only
            
            level0_headers.append(l0_val)
            level1_headers.append(l1_val)
            level2_headers.append(l2_val)
            
            col_data = []
            # row_labels now contains section_keys (e.g., "Average common equity::institutional securities")
            # We can look them up directly in row_data_map
            for section_key in row_labels:
                # Get the value using the section_key directly
                value = row_data_map.get(section_key, '')
                
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
        # Deduplicate adjacent identical headers for spanning (keep first, empty rest)
        # e.g., ["At Dec 31, 2024", "At Dec 31, 2024", "At Dec 31, 2024"] -> ["At Dec 31, 2024", "", ""]
        
        # Deduplicate Level 0 headers
        deduped_level0 = []
        prev_l0 = None
        for l0 in level0_headers:
            if l0 and l0 == prev_l0:
                deduped_level0.append('')  # Duplicate - empty it for spanning
            else:
                deduped_level0.append(l0)
                prev_l0 = l0 if l0 else prev_l0
        
        # Deduplicate Level 1 headers
        deduped_level1 = []
        prev_l1 = None
        for l1 in level1_headers:
            if l1 and l1 == prev_l1:
                deduped_level1.append('')  # Duplicate - empty it for spanning
            else:
                deduped_level1.append(l1)
                prev_l1 = l1 if l1 else prev_l1
        
        self._last_level0_headers = deduped_level0
        self._last_level1_headers = deduped_level1
        self._last_level2_headers = level2_headers
        
        result_df = pd.DataFrame(result_data)
        
        # Ensure column names are strings (prevent Excel from converting '2024' to 2024.0)
        # Use centralized ExcelUtils.ensure_string_header
        result_df.columns = [ExcelUtils.ensure_string_header(c) for c in result_df.columns]
        
        # Transpose if requested - creates multi-level column headers
        if transpose and len(result_df.columns) > 1:
            # First, identify category (section) rows and their associated line items
            # Category rows have text in first column but rest is empty
            category_to_items = {}  # Maps category -> list of line items under it
            current_category = "General"  # Default category if none found
            
            for row_label in row_labels:
                if row_label:
                    label_str = str(row_label).strip()
                    
                    # Check if this row is a category header (appears in section rows)
                    # Category rows are typically empty in data columns
                    is_category = False
                    for table_info in tables:
                        df_check = table_info['data']
                        if len(df_check) > 3:
                            for idx in range(3, len(df_check)):
                                row = df_check.iloc[idx]
                                first_cell = str(row.iloc[0]).strip() if pd.notna(row.iloc[0]) else ''
                                if first_cell == label_str:
                                    rest_empty = all(pd.isna(v) or str(v).strip() in ['', 'nan'] 
                                                    for v in row.iloc[1:])
                                    if rest_empty:
                                        is_category = True
                                        break
                            break
                    
                    if is_category:
                        current_category = label_str
                        if current_category not in category_to_items:
                            category_to_items[current_category] = []
                    else:
                        # This is a line item under the current category
                        if current_category not in category_to_items:
                            category_to_items[current_category] = []
                        category_to_items[current_category].append(label_str)
            
            # Transpose the DataFrame
            result_df = result_df.set_index('Row Label')
            result_df = result_df.T
            result_df.index.name = 'Dates'
            result_df = result_df.reset_index()
            
            # Create multi-level column headers
            # Build (Category, LineItem) tuples for each column
            # Use title() for proper capitalization
            new_columns = []
            for col in result_df.columns:
                col_str = str(col)
                if col_str == 'Dates':
                    new_columns.append(('', 'Dates'))  # First column
                else:
                    # Find which category this line item belongs to
                    found_category = 'General'
                    for category, items in category_to_items.items():
                        if col_str in items or ExcelUtils.clean_footnote_references(col_str) in items:
                            found_category = category
                            break
                    # Apply title() for proper capitalization
                    category_display = found_category.title() if found_category else ''
                    line_item_display = ExcelUtils.clean_footnote_references(col_str).title()
                    new_columns.append((category_display, line_item_display))
            
            # Create MultiIndex columns
            result_df.columns = pd.MultiIndex.from_tuples(new_columns, names=['Category', 'Line Item'])
            
            # Convert Dates column values to QnYYYY format for traceability
            # e.g., 'Three Months Ended March 31, 2024' -> '3QTD2024'
            dates_col = ('', 'Dates')
            # Check if column exists without triggering lexsort warning
            col_list = list(result_df.columns)
            if dates_col in col_list:
                col_idx = col_list.index(dates_col)
                for row_idx in range(len(result_df)):
                    val = result_df.iloc[row_idx, col_idx]
                    if val is not None and str(val).strip():
                        result_df.iloc[row_idx, col_idx] = MetadataBuilder.convert_to_qn_format(str(val))
        
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
        
        # === BUILD METADATA ROWS (Column A only) ===
        # Rows 1-12: Simple key-value metadata in column A
        # Row 13+: Actual table with headers (L0, L1, L2) then data
        
        def _convert_header_value(val):
            """Convert header value to clean string."""
            if val is None or val == '':
                return ''
            return ExcelUtils.ensure_string_header(val)
        
        # Prepare column header lists with converted values
        l0_headers = [_convert_header_value(h) for h in self._last_level0_headers]
        l1_headers = [_convert_header_value(h) for h in self._last_level1_headers]
        l2_headers = [_convert_header_value(h) for h in self._last_level2_headers]
        
        # Ensure header lists match column count (pad or trim)
        col_count = len(result_df.columns)
        
        def _ensure_length(headers, target_len):
            """Ensure headers list has exactly target_len elements."""
            if len(headers) < target_len:
                return headers + [''] * (target_len - len(headers))
            elif len(headers) > target_len:
                return headers[:target_len]
            return headers
        
        l0_headers = _ensure_length(l0_headers, col_count)
        l1_headers = _ensure_length(l1_headers, col_count)
        l2_headers = _ensure_length(l2_headers, col_count)
        
        # Build table title
        display_title = f"{section} - {original_title}" if section else original_title
        display_title = ExcelUtils.fix_ocr_broken_words(display_title)
        display_title = re.sub(r'\s+', ' ', display_title).strip()
        
        # Create TableMetadata container for MetadataBuilder
        table_metadata = TableMetadata(
            category_parent=row_headers_l1[:5] if row_headers_l1 else [],
            line_items=row_headers_l2[:10] if row_headers_l2 else [],
            product_entity=products[:5] if products else [],
            column_header_l1=l0_headers,
            column_header_l2=l1_headers,
            column_header_l3=l2_headers,
            table_title=display_title,
            sources=all_sources,
            section=''  # Already included in display_title
        )
        
        # Build metadata using MetadataBuilder (12 rows with summaries in column A)
        columns = list(result_df.columns)
        first_col = columns[0] if columns else 'Row Label'
        metadata_df = MetadataBuilder.build_metadata_dataframe(table_metadata, columns, first_col)
        
        # Build table header rows (L0, L1, L2 - spread across columns)
        # These will be part of the actual table, not metadata
        has_l0 = any(h for h in l0_headers[1:] if h)  # Skip first col
        has_l1 = any(h for h in l1_headers[1:] if h)  # Skip first col
        
        header_frames = []
        if has_l0:
            level0_df = pd.DataFrame([l0_headers], columns=columns, dtype=str)
            header_frames.append(level0_df)
        if has_l1:
            level1_df = pd.DataFrame([l1_headers], columns=columns, dtype=str)
            header_frames.append(level1_df)
        # L2 (years/dates) is always present as table header
        level2_df = pd.DataFrame([l2_headers], columns=columns, dtype=str)
        header_frames.append(level2_df)
        
        # === CONCATENATE ALL FRAMES ===
        # Structure: metadata (12 rows) + table headers (L0/L1/L2) + data
        frames_to_concat = [metadata_df] + header_frames + [result_df]
        
        # Ensure all frames have compatible column structures before concat
        # This fixes "cannot join with no overlapping index names" errors
        normalized_frames = []
        for i, frame in enumerate(frames_to_concat):
            # Reset index to avoid index join issues
            frame = frame.reset_index(drop=True)
            # Flatten MultiIndex columns if present
            if isinstance(frame.columns, pd.MultiIndex):
                frame.columns = [' '.join(str(c) for c in col).strip() if isinstance(col, tuple) else str(col) for col in frame.columns]
            # Ensure columns are simple strings
            frame.columns = [str(c) for c in frame.columns]
            normalized_frames.append(frame)
        
        # Now concatenate with matching column names
        try:
            final_df = pd.concat(normalized_frames, ignore_index=True)
        except ValueError as e:
            # Fallback: align columns by position if names don't match
            logger.warning(f"Column name mismatch, using positional alignment: {e}")
            # Get max columns and use positional indexing
            max_cols = max(len(f.columns) for f in normalized_frames)
            aligned_frames = []
            for frame in normalized_frames:
                frame.columns = list(range(len(frame.columns)))
                aligned_frames.append(frame)
            final_df = pd.concat(aligned_frames, ignore_index=True)
            # Restore original column names from result_df
            final_df.columns = list(range(len(final_df.columns)))
        
        # Track header row count for cell merging later
        header_row_count = 12 + len(header_frames)
        
        # Fix header rows: Convert any float years (e.g., 2025.0) back to strings
        for row_idx in range(min(header_row_count, len(final_df))):
            for col_idx in range(len(final_df.columns)):
                val = final_df.iloc[row_idx, col_idx]
                if isinstance(val, float) and not pd.isna(val):
                    if val == int(val):
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
        """
        Add hyperlinks to consolidated workbook.
        
        Delegates to ExcelFormatter for centralized logic.
        """
        ExcelFormatter.add_hyperlinks(output_path, all_tables_by_full_title, title_to_sheet_name)
    
    def _apply_currency_format(
        self,
        output_path: Path,
        all_tables_by_full_title: Dict[str, List],
        title_to_sheet_name: Dict[str, dict]
    ) -> None:
        """
        Apply US currency number format to numeric data cells.
        
        Delegates to ExcelFormatter for centralized logic.
        """
        ExcelFormatter.apply_currency_format(output_path, all_tables_by_full_title, title_to_sheet_name)


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
