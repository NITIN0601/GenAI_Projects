"""
Excel Table Exporter with Index Sheet.

Exports extracted tables to multi-sheet Excel with:
- Index sheet with hyperlinks to each table sheet
- One sheet per unique table title
- Multiple tables with same title stacked with blank rows
- Back-links from each sheet to Index

Usage:
    from src.infrastructure.extraction.formatters.excel_exporter import get_excel_exporter
    
    exporter = get_excel_exporter()
    
    # Per-PDF export
    exporter.export_pdf_tables(tables, "10q0625.pdf")
    # -> data/processed/10q0625_tables.xlsx
    
    # Combined export (after all PDFs processed)
    exporter.export_combined_tables(all_tables)
    # -> data/extracted/all_tables_combined.xlsx
    
    # For consolidated multi-file merge, use:
    from src.infrastructure.extraction.consolidation.consolidated_exporter import get_consolidated_exporter
"""

__version__ = "2.1.0"
__author__ = "dundaymo"

import pandas as pd
from typing import List, Dict, Any, Optional
from pathlib import Path
from datetime import datetime
from collections import defaultdict
import re

from src.utils import get_logger
from src.core import get_paths
from src.infrastructure.extraction.formatters.header_detector import HeaderDetector
from src.infrastructure.extraction.exporters.base_exporter import BaseExcelExporter
from src.utils.excel_utils import ExcelUtils
from src.utils.metadata_builder import MetadataLabels
from src.utils.financial_domain import extract_quarter_from_header, extract_year_from_header, convert_year_to_q4_header

logger = get_logger(__name__)


class ExcelTableExporter(BaseExcelExporter):
    """
    Export extracted tables to multi-sheet Excel with Index.
    
    Features:
    - Index sheet with Source, PageNo, Table_ID, Location_ID, Table Title, Link
    - One sheet per unique table title (using Table_ID as sheet name)
    - Detailed header structure: Row Headers, Column Headers, Product/Entity
    - Same-title tables stacked with blank separator
    - Bidirectional hyperlinks (Index <-> Sheets)
    
    Inherits shared Excel utilities from BaseExcelExporter.
    Follows singleton pattern consistent with other managers.
    """
    
    def __init__(self):
        """Initialize exporter with paths from PathManager."""
        super().__init__()
        self.paths = get_paths()
        self.processed_dir = self.paths.data_dir / "processed"
        self.extracted_dir = self.paths.data_dir / "extracted"
        
        # Ensure directories exist
        self.processed_dir.mkdir(parents=True, exist_ok=True)
        self.extracted_dir.mkdir(parents=True, exist_ok=True)
    
    def export_pdf_tables(
        self,
        tables: List[Dict[str, Any]],
        source_pdf: str,
        output_dir: Optional[str] = None
    ) -> str:
        """
        Export tables from a single PDF to Excel.
        
        Args:
            tables: List of extracted table dictionaries with:
                - content: Table content (markdown or text)
                - metadata: Dict with page_no, table_title, etc.
            source_pdf: Source PDF filename
            output_dir: Override output directory
            
        Returns:
            Path to created Excel file
        """
        output_dir = Path(output_dir) if output_dir else self.processed_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate output filename
        pdf_name = Path(source_pdf).stem
        output_path = output_dir / f"{pdf_name}_tables.xlsx"
        
        return self._create_excel_workbook(tables, output_path, source_pdf)
    
    def export_combined_tables(
        self,
        all_tables: List[Dict[str, Any]],
        output_dir: Optional[str] = None
    ) -> str:
        """
        Export tables from all PDFs to single combined Excel.
        
        Groups tables by title across all sources.
        
        Args:
            all_tables: List of all extracted tables from all PDFs
            output_dir: Override output directory
            
        Returns:
            Path to created Excel file
        """
        output_dir = Path(output_dir) if output_dir else self.extracted_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d")
        output_path = output_dir / f"all_tables_combined_{timestamp}.xlsx"
        
        return self._create_excel_workbook(all_tables, output_path, "Combined")
    
    def _create_excel_workbook(
        self,
        tables: List[Dict[str, Any]],
        output_path: Path,
        source_label: str
    ) -> str:
        """
        Create Excel workbook with Index and table sheets.
        
        Args:
            tables: List of table dictionaries
            output_path: Output file path
            source_label: Label for source (PDF name or "Combined")
            
        Returns:
            Path to created file
        """
        if not tables:
            logger.warning("No tables to export")
            return ""
        
        try:
            # Group tables by title (returns dict with Table_ID as key)
            tables_by_title = self._group_tables_by_title(tables)
            
            # Create workbook
            with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
                # Create Index sheet first
                self._create_index_sheet(writer, tables, tables_by_title)
                
                # Create table sheets - use Table_ID as sheet name
                for table_id, title_tables in tables_by_title.items():
                    self._create_table_sheet(writer, table_id, title_tables)
            
            # Add hyperlinks (requires reopening workbook)
            self._add_hyperlinks(output_path, tables_by_title)
            
            # Merge repeated header cells to match PDF layout
            self._merge_repeated_header_cells(output_path, tables_by_title)
            
            logger.info(f"Exported {len(tables)} tables to {output_path}")
            return str(output_path)
            
        except Exception as e:
            logger.error(f"Failed to export tables: {e}", exc_info=True)
            return ""
    
    def _group_tables_by_title(
        self,
        tables: List[Dict[str, Any]]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Group tables by their logical table (Section + Title).
        
        IMPORTANT: Tables with the same title but different sections are DIFFERENT tables.
        E.g., "Income Statement Info" under "Institutional Securities" vs "Wealth Management"
        should NOT be merged.
        
        Returns dict with Table_ID as key to avoid sheet name collisions.
        """
        groups = defaultdict(list)
        logical_table_ids = {}
        next_table_id = 1
        
        for table in tables:
            metadata = table.get('metadata', {})
            title = metadata.get('table_title', 'Untitled')
            section = metadata.get('section_name', '')  # Get section name
            
            # Clean title to identify logical table (remove row ranges)
            cleaned_title = self._clean_title_for_grouping(title)
            normalized_title = self._normalize_title_for_grouping(cleaned_title)
            
            # Create grouping key: Section + Title
            # This ensures same-titled tables in different sections stay separate
            # Fix OCR broken words and normalize whitespace
            section_fixed = ExcelUtils.fix_ocr_broken_words(section) if section else ''
            section_normalized = re.sub(r'\s+', ' ', section_fixed).strip().lower() if section_fixed else ''
            if section_normalized:
                grouping_key = f"{section_normalized}::{normalized_title}"
            else:
                grouping_key = f"default::{normalized_title}"
            
            # Assign Table_ID based on unique Section + Title combination
            if grouping_key not in logical_table_ids:
                logical_table_ids[grouping_key] = str(next_table_id)
                next_table_id += 1
            
            table_id = logical_table_ids[grouping_key]
            
            # Store the table_id and section in metadata for later use
            if 'metadata' not in table:
                table['metadata'] = {}
            table['metadata']['_assigned_table_id'] = table_id
            table['metadata']['_cleaned_title'] = cleaned_title
            table['metadata']['_section'] = section
            table['metadata']['_grouping_key'] = grouping_key
            
            # Group by Table_ID instead of sanitized title
            groups[table_id].append(table)
        
        return dict(groups)
    
    def _clean_title_for_grouping(self, title: str) -> str:
        """
        Clean title for grouping - remove row ranges and chunk indicators.
        
        This ensures chunks of the same table are grouped together:
        - "Income Statement (Rows 1-10)" -> "Income Statement"
        - "Balance Sheet (Rows 8-15)" -> "Balance Sheet"
        """
        if not title:
            return "Untitled"
        
        # Remove row ranges like "(Rows 1-10)" or "(Rows 8-17)"
        cleaned = re.sub(r'\s*\(Rows?\s*\d+[-–]\d+\)\s*$', '', title, flags=re.IGNORECASE)
        
        # Remove trailing numbers that might be footnotes
        cleaned = re.sub(r'\s+\d+\s*$', '', cleaned)
        
        # Remove trailing parenthesized numbers
        cleaned = re.sub(r'\s*\(\d+\)\s*$', '', cleaned)
        
        return cleaned.strip() or "Untitled"
    
    def _normalize_title_for_grouping(self, title: str) -> str:
        """
        Normalize title for case-insensitive grouping.
        Delegates to ExcelUtils after cleaning row ranges.
        """
        if not title:
            return "untitled"
        
        # First clean row ranges
        cleaned = self._clean_title_for_grouping(title)
        
        # Use ExcelUtils for the actual normalization
        return ExcelUtils.normalize_title_for_grouping(cleaned) or "untitled"
    
    def _sanitize_sheet_name(self, name: str) -> str:
        """Sanitize string for Excel sheet name. Delegates to ExcelUtils."""
        return ExcelUtils.sanitize_sheet_name(name)
    
    def _create_index_sheet(
        self,
        writer: pd.ExcelWriter,
        tables: List[Dict[str, Any]],
        tables_by_title: Dict[str, List[Dict[str, Any]]]
    ) -> None:
        """
        Create Index sheet with comprehensive table metadata.
        
        Columns: Source, PageNo, Table_ID, Location_ID, Section, Table Title, Link
        
        Location_ID = <pageNo>_<Table_IndexID_perpage>
        Section is included to show why tables with same title might be separate.
        """
        index_data = []
        
        # Track tables per page to generate Location_ID
        page_table_counts = {}
        
        # Track unique logical tables to assign Table_ID (Section + Title)
        logical_table_ids = {}
        next_table_id = 1
        
        for table in tables:
            metadata = table.get('metadata', {})
            title = metadata.get('table_title', 'Untitled')
            section = metadata.get('section_name', '')  # Get section name
            
            # Clean title to identify logical table (remove row ranges)
            cleaned_title = self._clean_title_for_grouping(title)
            normalized_title = self._normalize_title_for_grouping(cleaned_title)
            
            # Create grouping key: Section + Title (consistent with _group_tables_by_title)
            # Fix OCR broken words and normalize whitespace
            section_fixed = ExcelUtils.fix_ocr_broken_words(section) if section else ''
            section_normalized = re.sub(r'\s+', ' ', section_fixed).strip().lower() if section_fixed else ''
            if section_normalized:
                grouping_key = f"{section_normalized}::{normalized_title}"
            else:
                grouping_key = f"default::{normalized_title}"
            
            # Assign Table_ID based on unique Section + Title combination
            if grouping_key not in logical_table_ids:
                logical_table_ids[grouping_key] = str(next_table_id)
                next_table_id += 1
            
            table_id = logical_table_ids[grouping_key]
            
            # Get page number
            page_no = metadata.get('page_no', 'N/A')
            
            # Generate Location_ID as <pageNo>_<TableIndexID_perpage>
            if page_no != 'N/A':
                if page_no not in page_table_counts:
                    page_table_counts[page_no] = 0
                page_table_counts[page_no] += 1
                location_id = f"{page_no}_{page_table_counts[page_no]}"
            else:
                location_id = ''
            
            # Required columns per spec (now includes Section)
            # Fix OCR broken words and normalize whitespace
            section_clean = ExcelUtils.fix_ocr_broken_words(section) if section else ''
            section_clean = re.sub(r'\s+', ' ', section_clean).strip() if section_clean else ''
            index_data.append({
                'Source': metadata.get('source_doc', 'Unknown'),
                'PageNo': page_no,
                'Table_ID': table_id,
                'Location_ID': location_id,
                'Section': section_clean,  # Normalized Section column
                'Table Title': title,
                'Link': table_id  # Use Table_ID as link target (sheet name)
            })
        
        df = pd.DataFrame(index_data)
        
        # Ensure columns in correct order (now includes Section)
        REQUIRED_COLUMNS = ['Source', 'PageNo', 'Table_ID', 'Location_ID', 'Section', 'Table Title', 'Link']
        cols_to_keep = [c for c in REQUIRED_COLUMNS if c in df.columns]
        if cols_to_keep:
            df = df[cols_to_keep]
        
        df.to_excel(writer, sheet_name='Index', index=False)
        
        # Auto-adjust column widths with smart sizing
        worksheet = writer.sheets['Index']
        for idx, col in enumerate(df.columns):
            col_letter = self._get_column_letter(idx)
            
            max_content_len = df[col].astype(str).map(len).max() if len(df) > 0 else 0
            header_len = len(col)
            max_len = max(max_content_len, header_len) + 2
            
            # Apply reasonable limits based on column type
            if col == 'Table Title':
                max_len = min(max_len, 60)
            elif col == 'Section':
                max_len = min(max_len, 25)  # Section column
            elif col in ['Source', 'Table_ID', 'Location_ID']:
                max_len = min(max_len, 25)
            elif col == 'PageNo':
                max_len = min(max_len, 10)
            elif col == 'Link':
                max_len = min(max_len, 15)
            else:
                max_len = min(max_len, 20)
            
            worksheet.column_dimensions[col_letter].width = max_len
    
    def _get_column_letter(self, idx: int) -> str:
        """Convert column index to Excel column letter. Delegates to ExcelUtils."""
        return ExcelUtils.get_column_letter(idx)
    
    def _create_table_sheet(
        self,
        writer: pd.ExcelWriter,
        sheet_name: str,
        tables: List[Dict[str, Any]]
    ) -> None:
        """
        Create sheet for a specific table (identified by Table_ID).
        
        Sheet Structure:
        - Row 1: "← Back to Index" link
        - Row 2: Row Header (Level 1): ...
        - Row 3: Row Header (Level 2 - Sub): ... (if applicable)
        - Row 4: Product/Entity: ...
        - Row 5: Column Headers (Level 1): ...
        - Row 6: Column Headers (Level 2): ... (if applicable)
        - Row 7: <blank>
        - Row 8: Table Title: ...
        - Row 9: <blank>
        - Row 10+: Table data
        
        Args:
            writer: Excel writer
            sheet_name: Sheet name (Table_ID, e.g., "1", "2")
            tables: List of table chunks with same logical table
        """
        all_rows = []
        
        # Row 1: Add "Back to Index" link placeholder
        all_rows.append(['← Back to Index'])
        
        # Process each table with its own full metadata block
        for i, table in enumerate(tables):
            # Add 2 blank lines before each table (except first)
            if i > 0:
                all_rows.append([])
                all_rows.append([])
            
            # Generate metadata + data rows for this table
            table_rows = self._generate_single_table_rows(table)
            all_rows.extend(table_rows)
        
        # Create DataFrame from all rows
        df = pd.DataFrame(all_rows)
        df.to_excel(writer, sheet_name=sheet_name, index=False, header=False)
    
    def _detect_column_header_levels(self, content: str) -> Dict[str, Any]:
        """
        Detect multi-level column headers from markdown table content.
        
        Delegates to HeaderDetector class.
        
        Returns:
            {
                'has_multi_level': bool,
                'level_1': List[str],  # Main/spanning headers
                'level_2': List[str]   # Sub-headers (typically with dates/years)
            }
        """
        return HeaderDetector.detect_column_header_levels(content)
    
    def _dedupe_preserve_order(self, items: List[str]) -> List[str]:
        """Deduplicate a list while preserving order. Delegates to HeaderDetector."""
        return HeaderDetector.dedupe_preserve_order(items)
    
    def _parse_table_content(self, content: str) -> pd.DataFrame:
        """Parse markdown/text table content to DataFrame."""
        from src.utils.table_utils import parse_markdown_table
        return parse_markdown_table(content, handle_colon_separator=False)
    
    def _generate_single_table_rows(self, table: Dict[str, Any]) -> List[List[Any]]:
        """
        Generate all rows (metadata + data) for a single table.
        
        This creates a complete block for one table:
        - Row Header (Level 1): ...
        - Row Header (Level 2): ...
        - Product/Entity: ...
        - Column Header (Level 1): ...
        - Column Header (Level 2): ...
        - Year(s): ...
        - [blank]
        - Table Title: ...
        - Source: ...
        - [Column headers row]
        - [Data rows...]
        
        Args:
            table: Single table dict with 'content' and 'metadata'
            
        Returns:
            List of rows to add to the sheet
        """
        rows = []
        metadata = table.get('metadata', {})
        display_title = metadata.get('_cleaned_title', metadata.get('table_title', 'Untitled'))
        
        # Parse table content
        table_df = self._parse_table_content(table.get('content', ''))
        
        # === COLLECT ROW HEADERS ===
        all_row_headers = []      # L1 - section headers
        all_row_sub_headers = []  # L2 - data row labels
        
        if not table_df.empty and len(table_df.columns) > 0:
            for idx, val in enumerate(table_df.iloc[:, 0]):
                if pd.notna(val) and str(val).strip():
                    row_label = str(val).strip()
                    
                    # Check if this row has numeric data in subsequent columns
                    has_numeric_data = False
                    all_same_text = True
                    
                    if len(table_df.columns) > 1:
                        row_data = table_df.iloc[idx, 1:]
                        for cell_val in row_data:
                            if pd.notna(cell_val) and str(cell_val).strip():
                                cell_str = str(cell_val).strip().lower()
                                if cell_str in ['nan', '', '-', '—']:
                                    continue
                                
                                if cell_str != row_label.lower():
                                    all_same_text = False
                                
                                cell_clean = str(cell_val).strip()
                                if (cell_clean.startswith('$') or 
                                    cell_clean.startswith('(') or
                                    (cell_clean and cell_clean[0].isdigit()) or
                                    any(c.isdigit() for c in cell_clean)):
                                    has_numeric_data = True
                                    break
                    
                    is_section_header = (not has_numeric_data) or all_same_text
                    
                    if is_section_header and len(table_df.columns) > 1:
                        all_row_headers.append(row_label)
                    else:
                        all_row_sub_headers.append(row_label)
        
        # Filter headers (keep original values without cleaning - cleaning happens at display time)
        filtered_row_headers = []
        for h in all_row_headers:
            if h and h.lower() not in ['nan', 'none', '']:
                filtered_row_headers.append(h)
        
        filtered_row_sub_headers = []
        for h in all_row_sub_headers:
            if h and h.lower() not in ['nan', 'none', '']:
                filtered_row_sub_headers.append(h)
        
        # Build L2 excluding L1 items
        seen_l1 = set(filtered_row_headers)
        l2_row_headers = [h for h in filtered_row_sub_headers if h not in seen_l1]
        
        # Clean footnotes ONLY for display (preserves original values above for matching)
        display_row_headers = [ExcelUtils.clean_footnote_references(h) for h in filtered_row_headers if h]
        display_l2_row_headers = [ExcelUtils.clean_footnote_references(h) for h in l2_row_headers if h]
        
        # Category (Parent) - section headers (formerly Row Header Level 1)
        row_headers_str = ', '.join(display_row_headers) if display_row_headers else ''
        rows.append([f"Category (Parent): {row_headers_str}"])
        
        # Line Items - data row labels (formerly Row Header Level 2)
        row_sub_headers_str = ', '.join(display_l2_row_headers) if display_l2_row_headers else ''
        rows.append([f"Line Items: {row_sub_headers_str}"])
        
        # Use shared utility for unit detection
        from src.utils.financial_domain import is_unit_indicator
        
        unique_entities = []
        seen_entities = set()
        for h in display_l2_row_headers:
            if h and h not in seen_entities and not is_unit_indicator(h):
                unique_entities.append(h)
                seen_entities.add(h)
        
        entities_str = ', '.join(unique_entities) if unique_entities else ''
        rows.append([f"Product/Entity: {entities_str}"])
        
        # === COLUMN HEADERS ===
        detected_years = set()
        headers_info = self._detect_column_header_levels(table.get('content', ''))
        source_doc = metadata.get('source_doc', '')
        
        # Get all header levels
        level_0 = self._dedupe_preserve_order(headers_info.get('level_0', []))
        level_1 = self._dedupe_preserve_order(headers_info.get('level_1', []))
        level_2_raw = self._dedupe_preserve_order(headers_info.get('level_2', []))
        
        # For 10-K reports with year-only headers (no period type), convert to Q4 format
        # Only convert if level_1 is empty (no "Three Months Ended" etc.)
        level_2 = []
        for h in level_2_raw:
            if not level_1:  # No period type headers, just year-only
                converted = convert_year_to_q4_header(str(h), source_doc)
                level_2.append(converted)
            else:
                level_2.append(h)
        
        # Extract years from all header levels
        for header in level_0 + level_1 + level_2:
            year_match = re.search(r'(20\d{2})', str(header))
            if year_match:
                detected_years.add(year_match.group(1))
        
        # Main Header - only show if present (top spanning header, Level 0)
        if level_0:
            level_0_str = ', '.join(level_0)
            rows.append([f"{MetadataLabels.MAIN_HEADER} {level_0_str}"])
        
        # Period Type - date periods or main headers (Level 1)
        level_1_str = ', '.join(level_1) if level_1 else ''
        rows.append([f"{MetadataLabels.PERIOD_TYPE} {level_1_str}"])
        
        # Year(s) - years or sub-headers (Level 2)
        level_2_str = ', '.join(level_2) if level_2 else ''
        rows.append([f"{MetadataLabels.YEARS} {level_2_str}"])
        
        # Year/Quarter - format as PERIOD_TYPE,YEAR (e.g., QTD3,2024)
        detected_periods = []
        seen_periods = set()
        
        for header in level_1 + level_0:
            quarter_type = extract_quarter_from_header(str(header))
            year = extract_year_from_header(str(header))
            
            if quarter_type and year:
                period_key = f"{quarter_type},{year}"
                if period_key not in seen_periods:
                    detected_periods.append(period_key)
                    seen_periods.add(period_key)
            elif quarter_type:
                for y in sorted(detected_years, reverse=True):
                    period_key = f"{quarter_type},{y}"
                    if period_key not in seen_periods:
                        detected_periods.append(period_key)
                        seen_periods.add(period_key)
        
        # Fallback: use metadata quarter/year if no headers detected
        if not detected_periods:
            quarter = metadata.get('quarter', '')
            year_from_meta = metadata.get('year', '')
            if quarter and year_from_meta:
                detected_periods.append(f"{quarter},{year_from_meta}")
            elif detected_years:
                for y in sorted(detected_years, reverse=True):
                    detected_periods.append(y)
        
        periods_str = ', '.join(detected_periods) if detected_periods else ''
        rows.append([f"{MetadataLabels.YEAR_QUARTER} {periods_str}"])
        
        # Blank row
        rows.append([])
        
        # Table Title
        rows.append([f"{MetadataLabels.TABLE_TITLE} {display_title}"])
        
        # Source with page number in format: source_pg#
        source_doc = metadata.get('source_doc', 'Unknown')
        page_no = metadata.get('page_no', 'N/A')
        # Format: 10q0625_pg5
        source_info = f"{MetadataLabels.SOURCE} {source_doc}_pg{page_no}"
        if metadata.get('year'):
            source_info += f", {metadata.get('year')}"
        if metadata.get('quarter'):
            source_info += f" {metadata.get('quarter')}"
        rows.append([source_info])
        
        # Empty row after Source for visual separation
        rows.append([])
        
        # === TABLE DATA ===
        if not table_df.empty:
            # Column headers
            def clean_header(c):
                if pd.isna(c):
                    return ''
                if isinstance(c, float) and c == int(c):
                    return str(int(c))
                return str(c)
            rows.append([clean_header(c) for c in table_df.columns])
            
            # Data rows with L1 cleaning
            for _, row in table_df.iterrows():
                cleaned_row = []
                is_l1_row = False
                
                # Check if L1 row
                if len(row) > 1:
                    first_val = str(row.iloc[0]).strip() if pd.notna(row.iloc[0]) else ''
                    if first_val:
                        has_numeric = False
                        all_same = True
                        for v in row.iloc[1:]:
                            if pd.notna(v):
                                v_str = str(v).strip()
                                if v_str and v_str.lower() not in ['nan', '', '-', '—']:
                                    if v_str.lower() != first_val.lower():
                                        all_same = False
                                    if (v_str.startswith('$') or v_str.startswith('(') or 
                                        (v_str and v_str[0].isdigit()) or any(c.isdigit() for c in v_str)):
                                        has_numeric = True
                        is_l1_row = all_same or not has_numeric
                
                for i, v in enumerate(row):
                    if pd.isna(v):
                        cleaned_row.append('')
                    elif is_l1_row and i > 0:
                        first_val = str(row.iloc[0]).strip() if pd.notna(row.iloc[0]) else ''
                        v_str = str(v).strip()
                        if v_str.lower() == first_val.lower():
                            cleaned_row.append('')
                        else:
                            cleaned_row.append(ExcelUtils.clean_cell_value(v))
                    elif i == 0:
                        # First column (row label) - clean footnotes
                        cleaned_row.append(ExcelUtils.clean_footnote_references(str(v)))
                    else:
                        # Data cells - clean year floats
                        cleaned_row.append(ExcelUtils.clean_cell_value(v))
                rows.append(cleaned_row)
        
        return rows
    
    def _add_hyperlinks(
        self,
        output_path: Path,
        tables_by_title: Dict[str, List[Dict[str, Any]]]
    ) -> None:
        """
        Add hyperlinks to workbook (Index <-> Sheets).
        
        Sheet names are now Table_IDs (e.g., "1", "2", "3"), so linking is simpler.
        """
        try:
            from openpyxl import load_workbook
            from openpyxl.styles import Font
            
            wb = load_workbook(output_path)
            
            # Add hyperlinks in Index sheet
            index_sheet = wb['Index']
            
            # Find the Link column index dynamically
            header_row = [index_sheet.cell(row=1, column=c).value for c in range(1, index_sheet.max_column + 1)]
            link_col = None
            for i, h in enumerate(header_row, start=1):
                if isinstance(h, str) and h.strip().lower() == 'link':
                    link_col = i
                    break
            
            if link_col is None:
                logger.warning("Link column not found in Index sheet")
                link_col = -1
            
            for row in range(2, index_sheet.max_row + 1):  # Skip header
                if link_col == -1:
                    break
                cell = index_sheet.cell(row=row, column=link_col)
                raw_value = cell.value
                
                # Link value is Table_ID (e.g., "1", "2", "3")
                table_id = None
                if raw_value is not None:
                    try:
                        raw_str = str(raw_value).strip()
                    except Exception:
                        raw_str = ''
                    
                    if raw_str.startswith('→'):
                        table_id = raw_str.lstrip('→').strip()
                    else:
                        table_id = raw_str
                
                if table_id:
                    # Sheet name is simply the Table_ID
                    sheet_name = table_id
                    
                    if sheet_name in wb.sheetnames:
                        cell.hyperlink = f"#'{sheet_name}'!A1"
                        cell.value = f"→ {sheet_name}"
                        cell.font = Font(color="0000FF", underline="single")
                    else:
                        logger.warning(f"Sheet '{sheet_name}' not found in workbook")
            
            # Add back-links in each table sheet
            for sheet_name in tables_by_title.keys():
                if sheet_name in wb.sheetnames:
                    sheet = wb[sheet_name]
                    cell = sheet.cell(row=1, column=1)
                    cell.hyperlink = "#'Index'!A1"
                    cell.value = "← Back to Index"
                    cell.font = Font(color="0000FF", underline="single")
            
            wb.save(output_path)
            
        except Exception as e:
            logger.error(f"Failed to add hyperlinks: {e}")
    
    def _merge_repeated_header_cells(
        self,
        output_path: Path,
        tables_by_title: Dict[str, List[Dict[str, Any]]]
    ) -> None:
        """
        Merge adjacent cells with same values in header rows.
        
        This makes Excel output match PDF layout where headers span multiple columns.
        For example: "Three Months Ended" | "Three Months Ended" → merged cell
        """
        try:
            from openpyxl import load_workbook
            from openpyxl.styles import Alignment
            
            wb = load_workbook(output_path)
            
            for sheet_name in tables_by_title.keys():
                if sheet_name not in wb.sheetnames:
                    continue
                    
                ws = wb[sheet_name]
                
                # Find ALL rows that start with "Source:" and merge their header rows
                # (Multiple tables with same title can be stacked on one sheet)
                for row_num in range(1, ws.max_row + 1):
                    cell_value = ws.cell(row=row_num, column=1).value
                    if cell_value and str(cell_value).startswith('Source:'):
                        # Skip the blank row after Source: - headers start 2 rows after
                        # Sheet structure: Source (row N) -> blank (N+1) -> headers (N+2, N+3, N+4...)
                        # Tables can have up to 3 levels of column headers that need merging
                        for header_offset in range(2, 5):  # Check rows +2, +3, +4
                            header_row = row_num + header_offset
                            if header_row <= ws.max_row:
                                # Only merge if this row looks like a header (has repeated values)
                                self._merge_row_cells(ws, header_row)
                        # Don't break - continue to find more table blocks
            
            wb.save(output_path)
            
        except Exception as e:
            logger.warning(f"Could not merge header cells: {e}")
    
    def _merge_row_cells(self, ws, row_num: int) -> None:
        """Merge adjacent cells with same non-empty values in a row."""
        from openpyxl.styles import Alignment
        from openpyxl.utils import get_column_letter
        
        max_col = ws.max_column
        if max_col < 2:
            return
        
        col = 2  # Start from column B (skip column A which is row labels)
        while col <= max_col:
            cell_value = ws.cell(row=row_num, column=col).value
            if not cell_value:
                col += 1
                continue
            
            # Find how many adjacent cells have the same value
            end_col = col
            while end_col < max_col:
                next_value = ws.cell(row=row_num, column=end_col + 1).value
                if next_value and str(next_value).strip() == str(cell_value).strip():
                    end_col += 1
                else:
                    break
            
            # If we found repeated cells, merge them
            if end_col > col:
                start_letter = get_column_letter(col)
                end_letter = get_column_letter(end_col)
                merge_range = f"{start_letter}{row_num}:{end_letter}{row_num}"
                try:
                    ws.merge_cells(merge_range)
                    # Center the merged cell
                    ws.cell(row=row_num, column=col).alignment = Alignment(horizontal='center')
                except Exception:
                    pass  # Cell might already be merged
            
            col = end_col + 1

    def merge_processed_files(
        self,
        output_filename: str = "consolidated_tables.xlsx",
        transpose: bool = False
    ) -> dict:
        """
        Merge all processed xlsx files into a single consolidated report.
        
        NOTE: This method delegates to ConsolidatedExcelExporter for cleaner separation.
        For direct access to consolidation features, use:
            from src.infrastructure.extraction.consolidation.consolidated_exporter import get_consolidated_exporter
        
        Args:
            output_filename: Output filename for consolidated report
            transpose: If True, dates become rows (time-series format)
            
        Returns:
            Dict with path, tables_merged, sources_merged, sheet_names
        """
        from src.infrastructure.extraction.consolidation.consolidated_exporter import get_consolidated_exporter
        
        consolidated_exporter = get_consolidated_exporter()
        return consolidated_exporter.merge_processed_files(
            output_filename=output_filename,
            transpose=transpose
        )


# =============================================================================
# SINGLETON PATTERN
# =============================================================================

_excel_exporter: Optional[ExcelTableExporter] = None


def get_excel_exporter() -> ExcelTableExporter:
    """
    Get or create global Excel exporter instance.
    
    Returns:
        ExcelTableExporter singleton instance
    """
    global _excel_exporter
    
    if _excel_exporter is None:
        _excel_exporter = ExcelTableExporter()
    
    return _excel_exporter


def reset_excel_exporter() -> None:
    """Reset the exporter singleton (for testing)."""
    global _excel_exporter
    _excel_exporter = None
