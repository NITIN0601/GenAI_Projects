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
"""

import pandas as pd
from typing import List, Dict, Any, Optional
from pathlib import Path
from datetime import datetime
from collections import defaultdict
import re

from src.utils import get_logger
from src.core import get_paths

logger = get_logger(__name__)


class ExcelTableExporter:
    """
    Export extracted tables to multi-sheet Excel with Index.
    
    Features:
    - Index sheet with Source, Page, Title, Link
    - One sheet per unique table title
    - Same-title tables stacked with blank separator
    - Bidirectional hyperlinks (Index <-> Sheets)
    
    Follows singleton pattern consistent with other managers.
    """
    
    def __init__(self):
        """Initialize exporter with paths from PathManager."""
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
            # Group tables by title
            tables_by_title = self._group_tables_by_title(tables)
            
            # Create workbook
            with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
                # Create Index sheet first
                self._create_index_sheet(writer, tables, tables_by_title)
                
                # Create table sheets
                for title, title_tables in tables_by_title.items():
                    self._create_table_sheet(writer, title, title_tables)
            
            # Add hyperlinks (requires reopening workbook)
            self._add_hyperlinks(output_path, tables_by_title)
            
            logger.info(f"Exported {len(tables)} tables to {output_path}")
            return str(output_path)
            
        except Exception as e:
            logger.error(f"Failed to export tables: {e}", exc_info=True)
            return ""
    
    def _group_tables_by_title(
        self,
        tables: List[Dict[str, Any]]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Group tables by their title (cleaned of row ranges)."""
        groups = defaultdict(list)
        
        for table in tables:
            metadata = table.get('metadata', {})
            title = metadata.get('table_title', 'Untitled')
            
            # Clean title to remove row ranges before grouping
            title = self._clean_title_for_grouping(title)
            
            # Normalize title for sheet name
            title = self._sanitize_sheet_name(title)
            groups[title].append(table)
        
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
        
        Ensures tables like:
        - "Difference Between Contractual..."
        - "Difference between Contractual..."
        are grouped together.
        """
        if not title:
            return "untitled"
        
        # First clean row ranges
        cleaned = self._clean_title_for_grouping(title)
        
        # Convert to lowercase for case-insensitive matching
        normalized = cleaned.lower().strip()
        
        # Remove extra whitespace
        normalized = re.sub(r'\s+', ' ', normalized)
        
        return normalized or "untitled"
    
    def _sanitize_sheet_name(self, name: str) -> str:
        """
        Sanitize string for Excel sheet name.
        
        Excel sheet name rules:
        - Max 31 characters
        - No: [ ] : * ? / \
        """
        # Remove invalid characters
        sanitized = re.sub(r'[\[\]:*?/\\]', '', name)
        
        # Truncate to 31 characters
        if len(sanitized) > 31:
            sanitized = sanitized[:28] + "..."
        
        return sanitized.strip() or "Untitled"
    
    def _create_index_sheet(
        self,
        writer: pd.ExcelWriter,
        tables: List[Dict[str, Any]],
        tables_by_title: Dict[str, List[Dict[str, Any]]]
    ) -> None:
        """
        Create Index sheet with comprehensive table metadata.
        
        Includes all metadata fields organized in logical groups:
        - Core: Source, Page, Table ID
        - Temporal: Year, Quarter, Report Type
        - Structure: Row Count, Column Count, Headers
        - Financial: Units, Currency
        - Quality: Quality Score, Confidence, Backend
        - Link: Hyperlink to table sheet
        """
        index_data = []
        
        for table in tables:
            metadata = table.get('metadata', {})
            title = metadata.get('table_title', 'Untitled')
            sanitized_title = self._sanitize_sheet_name(self._clean_title_for_grouping(title))
            
            # Extract all available metadata fields
            index_data.append({
                # === Core Document Info ===
                'Source': metadata.get('source_doc', 'Unknown'),
                'Page': metadata.get('page_no', 'N/A'),
                'Table ID': metadata.get('table_id', ''),
                'Table Title': title,
                'Original Title': metadata.get('original_table_title', ''),
                
                # === Temporal Info ===
                'Year': metadata.get('year', ''),
                'Quarter': metadata.get('quarter', ''),
                'Report Type': metadata.get('report_type', ''),
                'Fiscal Period': metadata.get('fiscal_period', ''),
                
                # === Table Classification ===
                'Table Type': metadata.get('table_type', ''),
                'Statement Type': metadata.get('statement_type', ''),
                
                # === Table Structure ===
                'Row Count': metadata.get('row_count', ''),
                'Column Count': metadata.get('column_count', ''),
                'Column Headers': metadata.get('column_headers', ''),
                'Has Multi-Level Headers': metadata.get('has_multi_level_headers', ''),
                
                # === Financial Context ===
                'Units': metadata.get('units', ''),
                'Currency': metadata.get('currency', ''),
                
                # === Quality Metrics ===
                'Quality Score': metadata.get('quality_score', ''),
                'Confidence': metadata.get('extraction_confidence', ''),
                'Extraction Backend': metadata.get('extraction_backend', ''),
                
                # === Company Info ===
                'Company Name': metadata.get('company_name', ''),
                'Company Ticker': metadata.get('company_ticker', ''),
                
                # === Navigation ===
                'Link': sanitized_title  # Will be converted to hyperlink later
            })
        
        df = pd.DataFrame(index_data)
        df.to_excel(writer, sheet_name='Index', index=False)
        
        # Auto-adjust column widths with smart sizing
        worksheet = writer.sheets['Index']
        for idx, col in enumerate(df.columns):
            # Get column letter (handles columns beyond Z)
            col_letter = self._get_column_letter(idx)
            
            # Calculate width based on content
            max_content_len = df[col].astype(str).map(len).max() if len(df) > 0 else 0
            header_len = len(col)
            max_len = max(max_content_len, header_len) + 2
            
            # Apply reasonable limits based on column type
            if col in ['Table Title', 'Original Title', 'Column Headers']:
                max_len = min(max_len, 60)  # Wider for titles
            elif col in ['Source', 'Table ID']:
                max_len = min(max_len, 30)
            elif col in ['Link']:
                max_len = min(max_len, 35)
            else:
                max_len = min(max_len, 20)  # Standard columns
            
            worksheet.column_dimensions[col_letter].width = max_len
    
    def _get_column_letter(self, idx: int) -> str:
        """Convert column index to Excel column letter (0=A, 25=Z, 26=AA, etc.)."""
        result = ""
        while idx >= 0:
            result = chr(idx % 26 + 65) + result
            idx = idx // 26 - 1
        return result
    
    def _create_table_sheet(
        self,
        writer: pd.ExcelWriter,
        title: str,
        tables: List[Dict[str, Any]]
    ) -> None:
        """
        Create sheet for a specific table title.
        
        Multiple tables with same title are stacked with blank rows.
        """
        all_rows = []
        
        # Add "Back to Index" link placeholder in row 1
        all_rows.append(['← Back to Index', '', '', '', ''])
        all_rows.append([])  # Blank row after link
        
        for i, table in enumerate(tables):
            metadata = table.get('metadata', {})
            
            # Add source header for each table occurrence
            source_info = f"Source: {metadata.get('source_doc', 'Unknown')}, Page {metadata.get('page_no', 'N/A')}"
            if metadata.get('year'):
                source_info += f", {metadata.get('year')}"
            if metadata.get('quarter'):
                source_info += f" {metadata.get('quarter')}"
            
            all_rows.append([source_info])
            
            # Parse table content
            table_df = self._parse_table_content(table.get('content', ''))
            
            if not table_df.empty:
                # Add header row
                all_rows.append(list(table_df.columns))
                
                # Add data rows
                for _, row in table_df.iterrows():
                    all_rows.append(list(row))
            
            # Add blank rows between tables (except after last)
            if i < len(tables) - 1:
                all_rows.append([])
                all_rows.append([])
        
        # Create DataFrame from all rows
        df = pd.DataFrame(all_rows)
        df.to_excel(writer, sheet_name=title, index=False, header=False)
    
    def _parse_table_content(self, content: str) -> pd.DataFrame:
        """Parse markdown/text table content to DataFrame."""
        from src.utils.table_utils import parse_markdown_table
        return parse_markdown_table(content, handle_colon_separator=False)
    
    def _add_hyperlinks(
        self,
        output_path: Path,
        tables_by_title: Dict[str, List[Dict[str, Any]]]
    ) -> None:
        """Add hyperlinks to workbook (Index <-> Sheets)."""
        try:
            from openpyxl import load_workbook
            from openpyxl.styles import Font
            
            wb = load_workbook(output_path)
            
            # Add hyperlinks in Index sheet
            index_sheet = wb['Index']
            link_col = 6  # Column F (Link)
            
            for row in range(2, index_sheet.max_row + 1):  # Skip header
                cell = index_sheet.cell(row=row, column=link_col)
                raw_value = cell.value
                
                # Strip arrow prefix if present (from previous hyperlink or source)
                sheet_name = raw_value.replace('→ ', '').strip() if isinstance(raw_value, str) and raw_value.startswith('→') else raw_value
                
                if sheet_name and sheet_name in wb.sheetnames:
                    # Create hyperlink to sheet
                    cell.hyperlink = f"#'{sheet_name}'!A1"
                    cell.value = f"→ {sheet_name}"
                    cell.font = Font(color="0000FF", underline="single")
            
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


    def merge_processed_files(
        self,
        output_filename: str = "consolidated_tables.xlsx",
        transpose: bool = False
    ) -> str:
        """
        Merge all processed xlsx files into a single consolidated report.
        
        Reads all *_tables.xlsx files from data/processed/, merges tables
        by title (row-aligned), and adds metadata columns.
        
        Args:
            output_filename: Output filename for consolidated report
            transpose: If True, dates become rows (time-series format)
            
        Returns:
            Path to created consolidated Excel file
        """
        import glob
        from openpyxl import load_workbook
        
        # Find all processed xlsx files
        pattern = str(self.processed_dir / "*_tables.xlsx")
        xlsx_files = glob.glob(pattern)
        
        # Filter out temp files (start with ~$)
        xlsx_files = [f for f in xlsx_files if not Path(f).name.startswith('~$')]
        
        if not xlsx_files:
            logger.warning(f"No processed xlsx files found in {self.processed_dir}")
            return ""
        
        logger.info(f"Found {len(xlsx_files)} processed files to merge")
        
        # Collect all tables from all files with metadata
        # Key = full title (for display), value includes sheet_name for linking
        all_tables_by_full_title = defaultdict(list)
        title_to_sheet_name = {}  # Map full title -> sanitized sheet name
        
        for xlsx_path in xlsx_files:
            try:
                # Read Index sheet to get metadata INCLUDING full table titles
                index_df = pd.read_excel(xlsx_path, sheet_name='Index')
                
                # Get all sheet names except Index
                xl = pd.ExcelFile(xlsx_path)
                table_sheets = [s for s in xl.sheet_names if s != 'Index']
                
                # Create mapping from Link (sheet name) to full Table Title
                # Note: Link column may have arrow prefix "→ " from hyperlinks
                link_to_full_title = {}
                for _, idx_row in index_df.iterrows():
                    full_title = str(idx_row.get('Table Title', ''))
                    link = str(idx_row.get('Link', ''))
                    # Strip arrow prefix if present
                    if link.startswith('→ '):
                        link = link[2:]  # Remove "→ " prefix
                    if link and full_title:
                        link_to_full_title[link] = full_title
                
                for sheet_name in table_sheets:
                    # Get the FULL title from the Index by matching sheet name
                    full_title = link_to_full_title.get(sheet_name, None)
                    
                    if not full_title:
                        # Try partial match (sheet name should be in the keys)
                        for link_key, title in link_to_full_title.items():
                            if sheet_name == link_key or sheet_name in link_key:
                                full_title = title
                                break
                        if not full_title:
                            full_title = sheet_name  # Fallback
                    
                    # Find metadata for this sheet from Index - match by Table Title
                    matching_rows = index_df[
                        index_df['Table Title'].astype(str) == full_title
                    ]
                    
                    if len(matching_rows) > 0:
                        row = matching_rows.iloc[0]
                        # Get source and extract full title again if available
                        full_title = str(row.get('Table Title', full_title))
                        metadata = {
                            'source': row.get('Source', Path(xlsx_path).stem),
                            'year': row.get('Year', ''),
                            'quarter': row.get('Quarter', ''),
                            'report_type': self._detect_report_type(str(row.get('Source', ''))),
                        }
                    else:
                        metadata = {
                            'source': Path(xlsx_path).stem,
                            'year': '',
                            'quarter': '',
                            'report_type': '',
                        }
                    
                    # Read table content (skip first 2 rows which are back-link)
                    try:
                        table_df = pd.read_excel(xlsx_path, sheet_name=sheet_name, header=None)
                        # Skip back-link rows
                        if len(table_df) > 2:
                            table_df = table_df.iloc[2:].reset_index(drop=True)
                        
                        # Use NORMALIZED title as key for case-insensitive grouping
                        normalized_key = self._normalize_title_for_grouping(full_title)
                        
                        all_tables_by_full_title[normalized_key].append({
                            'data': table_df,
                            'metadata': metadata,
                            'sheet_name': sheet_name,
                            'original_title': full_title  # Preserve original for display
                        })
                        
                        # Map normalized key to first-seen title and sanitized sheet name
                        if normalized_key not in title_to_sheet_name:
                            # Clean arrow prefix from display title if present
                            clean_display = full_title.replace('→ ', '').strip() if full_title.startswith('→') else full_title
                            title_to_sheet_name[normalized_key] = {
                                'display_title': clean_display,  # First-seen title for display (clean)
                                'sheet_name': self._sanitize_sheet_name(clean_display)  # Sheet name without arrow
                            }
                            
                    except Exception as e:
                        logger.debug(f"Skipping sheet {sheet_name}: {e}")
                        
            except Exception as e:
                logger.error(f"Error reading {xlsx_path}: {e}")
        
        if not all_tables_by_full_title:
            logger.warning("No tables collected for merging")
            return ""
        
        # Create consolidated output
        output_path = self.extracted_dir / output_filename
        
        try:
            with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
                # Create Master Index with FULL titles
                self._create_consolidated_index(writer, all_tables_by_full_title, title_to_sheet_name)
                
                # Create merged sheets for each table title (using normalized key)
                for normalized_key, tables in all_tables_by_full_title.items():
                    mapping = title_to_sheet_name.get(normalized_key, {})
                    sheet_name = mapping.get('sheet_name', self._sanitize_sheet_name(normalized_key)) if isinstance(mapping, dict) else self._sanitize_sheet_name(normalized_key)
                    self._create_merged_table_sheet(writer, sheet_name, tables, transpose=transpose)
            
            # Add hyperlinks using sheet name mapping
            hyperlink_mapping = {}
            for normalized_key, tables in all_tables_by_full_title.items():
                mapping = title_to_sheet_name.get(normalized_key, {})
                sheet_name = mapping.get('sheet_name', self._sanitize_sheet_name(normalized_key)) if isinstance(mapping, dict) else self._sanitize_sheet_name(normalized_key)
                hyperlink_mapping[sheet_name] = tables
            self._add_hyperlinks(output_path, hyperlink_mapping)
            
            logger.info(f"Created consolidated report at {output_path}")
            logger.info(f"  - Tables merged: {len(all_tables_by_full_title)}")
            logger.info(f"  - Sources: {len(xlsx_files)}")
            
            return str(output_path)
            
        except Exception as e:
            logger.error(f"Failed to create consolidated report: {e}", exc_info=True)
            return ""
    
    def _detect_report_type(self, source: str) -> str:
        """Detect report type from source filename."""
        source_lower = source.lower()
        if '10k' in source_lower or '10-k' in source_lower:
            return '10-K'
        elif '10q' in source_lower or '10-q' in source_lower:
            return '10-Q'
        elif '8k' in source_lower or '8-k' in source_lower:
            return '8-K'
        return 'Unknown'
    
    def _create_consolidated_index(
        self,
        writer: pd.ExcelWriter,
        tables_by_full_title: Dict[str, List[Dict[str, Any]]],
        title_to_sheet_name: Dict[str, str]
    ) -> None:
        """
        Create master index for consolidated report with comprehensive metadata.
        
        Aggregates metadata across all sources for each table title.
        """
        index_data = []
        
        for normalized_key, tables in tables_by_full_title.items():
            sources = set()
            years = set()
            quarters = set()
            report_types = set()
            table_types = set()
            quality_scores = []
            
            for t in tables:
                meta = t['metadata']
                if meta.get('source'):
                    sources.add(str(meta['source']))
                if meta.get('year') and str(meta.get('year')) not in ['nan', 'NaN', '']:
                    years.add(str(int(meta['year'])) if isinstance(meta.get('year'), float) else str(meta.get('year')))
                if meta.get('quarter') and str(meta.get('quarter')) not in ['nan', 'NaN', '']:
                    quarters.add(str(meta['quarter']))
                if meta.get('report_type'):
                    report_types.add(str(meta['report_type']))
                if meta.get('table_type'):
                    table_types.add(str(meta['table_type']))
                if meta.get('quality_score'):
                    try:
                        quality_scores.append(float(meta['quality_score']))
                    except (ValueError, TypeError):
                        pass
            
            # Filter out any remaining empty or NaN values
            quarters = {q for q in quarters if q and q.lower() != 'nan'}
            years = {y for y in years if y and y.lower() != 'nan'}
            sources = {s for s in sources if s and s.lower() != 'nan'}
            report_types = {r for r in report_types if r and r.lower() != 'nan'}
            table_types = {t for t in table_types if t and t.lower() != 'nan'}
            
            # Calculate average quality score
            avg_quality = sum(quality_scores) / len(quality_scores) if quality_scores else None
            
            # Get display title and sheet name from mapping
            mapping = title_to_sheet_name.get(normalized_key, {})
            if isinstance(mapping, dict):
                display_title = mapping.get('display_title', normalized_key)
                sheet_name = mapping.get('sheet_name', self._sanitize_sheet_name(normalized_key))
            else:
                display_title = normalized_key
                sheet_name = self._sanitize_sheet_name(normalized_key)
            
            index_data.append({
                # === Core Info ===
                'Table Title': display_title,
                'Table Count': len(tables),
                
                # === Sources ===
                'Sources': ', '.join(sorted(sources)),
                'Report Types': ', '.join(sorted(report_types)),
                
                # === Temporal ===
                'Years': ', '.join(sorted(years)),
                'Quarters': ', '.join(sorted(quarters)),
                
                # === Classification ===
                'Table Type': ', '.join(sorted(table_types)) if table_types else '',
                
                # === Quality ===
                'Avg Quality': f"{avg_quality:.1f}" if avg_quality else '',
                
                # === Navigation ===
                'Link': sheet_name
            })
        
        df = pd.DataFrame(index_data)
        df = df.sort_values('Table Title')
        df.to_excel(writer, sheet_name='Index', index=False)
        
        # Auto-adjust column widths with smart sizing
        worksheet = writer.sheets['Index']
        for idx, col in enumerate(df.columns):
            col_letter = self._get_column_letter(idx)
            
            max_content_len = df[col].astype(str).map(len).max() if len(df) > 0 else 0
            header_len = len(col)
            max_len = max(max_content_len, header_len) + 2
            
            if col == 'Table Title':
                max_len = min(max_len, 70)
            elif col in ['Sources', 'Report Types']:
                max_len = min(max_len, 40)
            elif col == 'Link':
                max_len = min(max_len, 35)
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
        """
        Create merged sheet with tables from multiple sources.
        
        Performs HORIZONTAL merge:
        - First column (row labels) is the merge key
        - Uses ORIGINAL column headers from source tables
        - Sorts columns chronologically by date parsed from headers
        
        Args:
            writer: Excel writer
            title: Sheet title
            tables: List of table dictionaries
            transpose: If True, transpose so periods become rows (time-series)
        """
        if not tables:
            return
        
        # Collect all columns with their original headers and data
        all_columns = {}  # key: normalized header, value: {header: str, data: list, date_sort_key: tuple}
        row_labels = []
        
        for table_info in tables:
            df = table_info['data']
            meta = table_info['metadata']
            
            if df.empty or len(df.columns) < 2:
                continue
            
            # First column is row labels
            if not row_labels:
                row_labels = df.iloc[:, 0].tolist()
            else:
                # Merge row labels from this source (union)
                for val in df.iloc[:, 0].tolist():
                    if val not in row_labels and pd.notna(val):
                        row_labels.append(val)
            
            # Extract column headers from the dataframe
            # Headers may span multiple rows (e.g., "Three Months Ended June 30," + "2024")
            for col_idx in range(1, len(df.columns)):
                # Collect header parts from multiple rows (first 5 rows typically contain headers)
                header_parts = []
                for row_idx in range(min(5, len(df))):
                    val = df.iloc[row_idx, col_idx]
                    if pd.notna(val):
                        val_str = str(val).strip()
                        # Skip empty, NaN, $ symbol only, or placeholder values
                        if val_str and val_str != 'nan' and val_str not in ['$', '$,', '%', '%,', '-', '—']:
                            # Check if this looks like data (not a header)
                            # But allow year values (2020-2029) as headers
                            import re
                            is_year = bool(re.match(r'^20[2-3]\d$', val_str))  # Years 2020-2039
                            
                            # Data patterns: currency ($xxx), percentages (x%), large numbers (>4 digits)
                            is_currency = val_str.startswith('$') and any(c.isdigit() for c in val_str)
                            is_percentage = '%' in val_str and any(c.isdigit() for c in val_str)
                            # Only treat as number if it's more than 4 digits (not a year)
                            num_digits = sum(c.isdigit() for c in val_str)
                            is_large_number = num_digits > 4 and val_str.replace(',', '').replace('.', '').replace('-', '').replace('(', '').replace(')', '').isdigit()
                            
                            is_data = (is_currency or is_percentage or is_large_number) and not is_year
                            
                            if not is_data:
                                header_parts.append(val_str)
                            else:
                                # Stop at first data row
                                break
                
                # Combine header parts (e.g., "Three Months Ended June 30," + "2024")
                if header_parts:
                    # Dedupe while preserving order (e.g., if same value repeated)
                    seen = set()
                    unique_parts = []
                    for p in header_parts:
                        if p.lower() not in seen:
                            seen.add(p.lower())
                            unique_parts.append(p)
                    header = ' '.join(unique_parts)
                    
                    # Strip period prefixes - keep only the actual date
                    header = self._extract_date_from_header(header)
                else:
                    header = f"Col_{col_idx}"
                
                # Create sort key from header (parse date)
                sort_key = self._parse_date_from_header(header)
                
                # Normalize header for dedup (lowercase, strip)
                norm_header = header.lower().strip()
                
                # Get column data (skip header rows)
                col_data = df.iloc[:, col_idx].tolist()
                
                # Skip columns that are entirely empty/NaN (no useful data)
                non_empty_data = [x for x in col_data if pd.notna(x) and str(x).strip() and str(x).strip() != 'nan']
                # Also filter out header-like values (the header repeated as data)
                non_empty_data = [x for x in non_empty_data if str(x).strip() != header]
                
                if not non_empty_data:
                    # Column has no useful data, skip it
                    continue
                
                # Check if this column already exists (by content comparison)
                is_duplicate = False
                col_data_str = str([str(x).strip() for x in col_data])
                
                for existing_key, existing_val in all_columns.items():
                    existing_data_str = str([str(x).strip() for x in existing_val['data']])
                    if col_data_str == existing_data_str:
                        is_duplicate = True
                        break
                
                if not is_duplicate:
                    # Use header as key, but handle duplicates with different content
                    final_key = norm_header
                    counter = 1
                    while final_key in all_columns:
                        final_key = f"{norm_header}_{counter}"
                        counter += 1
                    
                    all_columns[final_key] = {
                        'header': header,
                        'data': col_data,
                        'sort_key': sort_key,
                        'source': meta.get('source', '')
                    }
        
        if not all_columns:
            pd.DataFrame([{'← Back to Index': ''}]).to_excel(writer, sheet_name=title, index=False)
            return
        
        # Sort columns by date (year, month)
        sorted_cols = sorted(
            all_columns.items(),
            key=lambda x: x[1]['sort_key']
        )
        
        # Build result dataframe
        result_data = {'Row Label': row_labels}
        
        for _, col_info in sorted_cols:
            header = col_info['header']
            data = col_info['data']
            
            # Pad data to match row_labels length
            if len(data) < len(row_labels):
                data = data + [''] * (len(row_labels) - len(data))
            elif len(data) > len(row_labels):
                data = data[:len(row_labels)]
            
            result_data[header] = data
        
        result_df = pd.DataFrame(result_data)
        
        # Transpose if requested (dates as rows, metrics as columns)
        if transpose and len(result_df.columns) > 1:
            # Set Row Label as index for proper transpose
            result_df = result_df.set_index('Row Label')
            result_df = result_df.T  # Transpose
            result_df.index.name = 'Period'
            result_df = result_df.reset_index()
            
            # Rename 'Period' column to 'Period' for clarity
            if 'Period' not in result_df.columns and len(result_df.columns) > 0:
                result_df = result_df.rename(columns={result_df.columns[0]: 'Period'})
        
        # Add back-link as first row
        first_col = result_df.columns[0] if len(result_df.columns) > 0 else 'Row Label'
        back_link_row = pd.DataFrame([{first_col: '← Back to Index'}])
        result_df = pd.concat([back_link_row, result_df], ignore_index=True)
        
        # Write to sheet
        result_df.to_excel(writer, sheet_name=title, index=False)
    
    def _parse_date_from_header(self, header: str) -> tuple:
        """
        Parse date from column header for sorting.
        
        Examples:
        - "At December 31, 2023" -> (2023, 12, 31)
        - "At June 30, 2024" -> (2024, 6, 30)
        - "At March 31, 2025" -> (2025, 3, 31)
        - "2024" -> (2024, 0, 0)
        """
        import re
        
        header_lower = header.lower()
        
        # Month mapping
        months = {
            'january': 1, 'jan': 1,
            'february': 2, 'feb': 2,
            'march': 3, 'mar': 3,
            'april': 4, 'apr': 4,
            'may': 5,
            'june': 6, 'jun': 6,
            'july': 7, 'jul': 7,
            'august': 8, 'aug': 8,
            'september': 9, 'sep': 9,
            'october': 10, 'oct': 10,
            'november': 11, 'nov': 11,
            'december': 12, 'dec': 12
        }
        
        # Extract year (20xx pattern)
        year_match = re.search(r'20\d{2}', header)
        year = int(year_match.group()) if year_match else 9999
        
        # Extract month
        month = 0
        for month_name, month_num in months.items():
            if month_name in header_lower:
                month = month_num
                break
        
        # Extract day
        day_match = re.search(r'\b(\d{1,2})\b', header)
        day = int(day_match.group(1)) if day_match and 1 <= int(day_match.group(1)) <= 31 else 0
        
        return (year, month, day)
    
    def _extract_date_from_header(self, header: str) -> str:
        """
        Extract just the date portion from a header, stripping period prefixes.
        
        Examples:
        - "Three Months Ended June 30, 2024" -> "June 30, 2024"
        - "Six Months Ended June 30, 2024" -> "June 30, 2024"
        - "At December 31, 2023" -> "December 31, 2023"
        - "2024" -> "2024"
        """
        import re
        
        # Prefixes to strip
        prefixes_to_remove = [
            r'three\s+months?\s+ended\s*',
            r'six\s+months?\s+ended\s*',
            r'nine\s+months?\s+ended\s*',
            r'twelve\s+months?\s+ended\s*',
            r'year\s+ended\s*',
            r'quarter\s+ended\s*',
            r'period\s+ended\s*',
            r'ended\s+',
            r'^at\s+',
            r'^as\s+of\s+',
        ]
        
        result = header
        for prefix in prefixes_to_remove:
            result = re.sub(prefix, '', result, flags=re.IGNORECASE)
        
        # Clean up extra whitespace and commas
        result = re.sub(r'\s+', ' ', result).strip()
        result = re.sub(r'^,\s*', '', result)  # Remove leading comma
        
        # If nothing left, return original
        return result if result else header
    
    def _remove_duplicate_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Remove duplicate columns by comparing entire column content.
        
        Uses hash of column values to detect duplicates dynamically.
        Keeps the first occurrence of each unique column.
        """
        if df.empty or len(df.columns) <= 1:
            return df
        
        # Keep track of seen column content hashes
        seen_hashes = {}
        columns_to_keep = []
        
        for col in df.columns:
            # Create hash of column content (convert to string for consistent hashing)
            col_data = df[col].fillna('').astype(str).str.strip()
            col_hash = hash(tuple(col_data.tolist()))
            
            if col_hash not in seen_hashes:
                seen_hashes[col_hash] = col
                columns_to_keep.append(col)
            # If duplicate, skip this column (don't add to columns_to_keep)
        
        # Return dataframe with only unique columns
        return df[columns_to_keep]
    
    def _order_columns_by_date(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Order columns by date (year first, then quarter).
        
        Dynamically parses date information from column names and first row values.
        Orders: 2023_Q1, 2023_Q2, ..., 2024_Q1, 2024_Q2, ...
        """
        if df.empty or len(df.columns) <= 1:
            return df
        
        def extract_date_info(col_name: str, col_data: pd.Series) -> tuple:
            """Extract year and quarter from column name or data for sorting."""
            import re
            
            # Try to extract year from column name (look for 20xx pattern to avoid matching doc codes like 10q0325)
            year_matches = re.findall(r'20\d{2}', str(col_name))
            year = int(year_matches[0]) if year_matches else 9999
            
            quarter_match = re.search(r'Q(\d)', str(col_name), re.IGNORECASE)
            quarter = int(quarter_match.group(1)) if quarter_match else 0
            
            # If no quarter found, try to extract from first non-empty data value
            if quarter == 0:
                for val in col_data.dropna().head(5):
                    val_str = str(val).lower()
                    # Look for month patterns
                    if 'march' in val_str or 'mar' in val_str:
                        quarter = 1
                        break
                    elif 'june' in val_str or 'jun' in val_str:
                        quarter = 2
                        break
                    elif 'september' in val_str or 'sep' in val_str:
                        quarter = 3
                        break
                    elif 'december' in val_str or 'dec' in val_str:
                        quarter = 4
                        break
            
            # Also try to extract year from data if not found in column name
            if year == 9999:
                for val in col_data.dropna().head(5):
                    val_str = str(val)
                    year_in_data = re.search(r'20\d{2}', val_str)
                    if year_in_data:
                        year = int(year_in_data.group())
                        break
            
            return (year, quarter, col_name)
        
        # Keep Row Label column first
        row_label_col = df.columns[0] if 'Row Label' in str(df.columns[0]) or 'label' in str(df.columns[0]).lower() else None
        
        # Get date info for all columns except row label
        other_cols = [c for c in df.columns if c != row_label_col] if row_label_col else list(df.columns)
        
        # Sort columns by (year, quarter, name)
        sorted_cols = sorted(
            other_cols,
            key=lambda c: extract_date_info(c, df[c])
        )
        
        # Reconstruct column order: Row Label first, then sorted columns
        if row_label_col:
            final_order = [row_label_col] + sorted_cols
        else:
            final_order = sorted_cols
        
        return df[final_order]


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
