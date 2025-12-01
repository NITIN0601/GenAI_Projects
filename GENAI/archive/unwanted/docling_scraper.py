"""
Advanced PDF scraper using Docling with intelligent layout detection.

This scraper implements the complete document processing pipeline:
1. Process each page individually with intelligent column detection
2. Extract all elements (tables, text, headings, figures) with reading order
3. Preserve complete table structure (row headers, column headers, data cells)
4. Link footnotes to cells
5. Normalize and standardize data

Key improvement: Uses content-based column detection instead of mechanical left/right split.
"""

from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions, TableStructureOptions
from docling.backend.pypdfium2_backend import PyPdfiumDocumentBackend
from docling.datamodel.document import TableCell
from docling_core.types.doc import TableData, DoclingDocument

from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
import re
import uuid
from collections import defaultdict

from models.enhanced_schemas import (
    EnhancedFinancialTable,
    EnhancedDocument,
    DocumentMetadata,
    ColumnHeader,
    RowHeader,
    DataCell,
    Footnote,
    Period,
    PageLayout
)
from scrapers.label_normalizer import get_label_normalizer
from scrapers.period_parser import get_period_parser
from scrapers.unit_converter import get_unit_converter


class DoclingPDFScraper:
    """
    Advanced PDF scraper using Docling with intelligent layout detection.
    
    Key features:
    - Intelligent page-level column detection (not mechanical split)
    - Complete table structure preservation
    - Row headers with indentation hierarchy
    - Column headers with multi-level support
    - Data cells with type preservation
    - Footnote linking
    - Period standardization
    - Unit conversion
    """
    
    def __init__(self, pdf_path: str):
        """
        Initialize Docling PDF scraper.
        
        Args:
            pdf_path: Path to PDF file
        """
        self.pdf_path = pdf_path
        self.filename = Path(pdf_path).name
        
        # Initialize utilities
        self.label_normalizer = get_label_normalizer()
        self.period_parser = get_period_parser()
        self.unit_converter = get_unit_converter()
        
        # Configure Docling converter
        self.converter = DocumentConverter(
            allowed_formats=[InputFormat.PDF],
            format_options={
                InputFormat.PDF: PdfFormatOption(
                    pipeline_options=PdfPipelineOptions(
                        do_ocr=True,  # Enable OCR for scanned pages
                        do_table_structure=True,  # Enable advanced table structure
                        table_structure_options=TableStructureOptions(
                            do_cell_matching=True,  # Match cells to structure
                            mode="accurate"  # Use accurate mode (slower but better)
                        )
                    )
                )
            }
        )
    
    def extract_document(self) -> EnhancedDocument:
        """
        Extract complete document structure with intelligent layout detection.
        
        Returns:
            EnhancedDocument with all tables and metadata
        """
        print(f"Processing {self.filename} with Docling...")
        
        # Convert PDF
        result = self.converter.convert(self.pdf_path)
        doc: DoclingDocument = result.document
        
        # Extract document-level metadata
        doc_metadata = self._extract_document_metadata(doc)
        
        # Process each page individually
        pages = []
        all_tables = []
        
        for page_no in range(1, doc_metadata.total_pages + 1):
            page_data = self._process_page_intelligent(doc, page_no)
            pages.append(page_data)
            
            # Collect tables from this page
            if 'tables' in page_data:
                all_tables.extend(page_data['tables'])
        
        # Detect and merge multi-page tables
        merged_tables = self._merge_multi_page_tables(all_tables)
        
        return EnhancedDocument(
            metadata=doc_metadata,
            pages=pages,
            tables=merged_tables
        )
    
    def _extract_document_metadata(self, doc: DoclingDocument) -> DocumentMetadata:
        """
        Extract document-level metadata.
        
        Args:
            doc: Docling document
        
        Returns:
            DocumentMetadata object
        """
        # Calculate file hash
        import hashlib
        with open(self.pdf_path, 'rb') as f:
            file_hash = hashlib.md5(f.read()).hexdigest()
        
        # Extract metadata from document
        # Note: Docling may not have all metadata, so we use patterns
        company_name = self._extract_company_name(doc)
        document_type = self._extract_document_type(self.filename)
        filing_date = self._extract_filing_date(doc)
        reporting_period = self._extract_reporting_period(self.filename)
        
        return DocumentMetadata(
            filename=self.filename,
            file_hash=file_hash,
            company_name=company_name,
            document_type=document_type,
            filing_date=filing_date,
            reporting_period=reporting_period,
            total_pages=len(doc.pages) if hasattr(doc, 'pages') else 1
        )
    
    def _extract_company_name(self, doc: DoclingDocument) -> Optional[str]:
        """Extract company name from document (heuristic)."""
        # Look for company name in first few pages
        # This is a simplified heuristic - could be improved
        return "Morgan Stanley"  # TODO: Extract from document
    
    def _extract_document_type(self, filename: str) -> Optional[str]:
        """Extract document type from filename."""
        filename_lower = filename.lower()
        if '10k' in filename_lower:
            return "10-K"
        elif '10q' in filename_lower:
            return "10-Q"
        return "Unknown"
    
    def _extract_filing_date(self, doc: DoclingDocument) -> Optional[str]:
        """Extract filing date from document."""
        # TODO: Extract from document metadata or text
        return None
    
    def _extract_reporting_period(self, filename: str) -> Optional[str]:
        """Extract reporting period from filename."""
        # Pattern: 10q0325.pdf -> March 2025
        match = re.search(r'10[qk](\d{2})(\d{2})', filename.lower())
        if match:
            month = int(match.group(1))
            year = 2000 + int(match.group(2))
            
            # Map month to quarter end date
            if month in [1, 2, 3]:
                return f"{year}-03-31"
            elif month in [4, 5, 6]:
                return f"{year}-06-30"
            elif month in [7, 8, 9]:
                return f"{year}-09-30"
            else:
                return f"{year}-12-31"
        
        return None
    
    def _process_page_intelligent(self, doc: DoclingDocument, page_no: int) -> Dict[str, Any]:
        """
        Intelligent page processing with content-based column detection.
        
        Key improvement: Instead of mechanical left/right split:
        1. Analyze text block positions and alignments
        2. Detect natural column boundaries based on white space
        3. Group elements by column
        4. Determine reading order within and across columns
        
        Args:
            doc: Docling document
            page_no: Page number (1-indexed)
        
        Returns:
            Page data dictionary
        """
        # Get all elements on this page
        elements = [
            item for item in doc.iterate_items()
            if hasattr(item, 'prov') and item.prov and item.prov[0].page_no == page_no
        ]
        
        if not elements:
            return {
                'page_no': page_no,
                'layout_type': 'empty',
                'columns': [],
                'elements': [],
                'tables': []
            }
        
        # Detect column layout intelligently
        layout_info = self._detect_column_layout(elements, page_no)
        
        # Group elements by column
        columns = self._group_elements_by_column(elements, layout_info)
        
        # Determine reading order
        ordered_elements = self._determine_reading_order(columns, layout_info)
        
        # Extract tables with full structure
        tables = []
        for elem in ordered_elements:
            if elem.label == 'table':
                try:
                    table = self._extract_table_structure(elem, page_no)
                    if table:
                        tables.append(table)
                except Exception as e:
                    print(f"Warning: Failed to extract table on page {page_no}: {e}")
        
        return {
            'page_no': page_no,
            'layout_type': layout_info['type'],
            'columns': layout_info['columns'],
            'elements': ordered_elements,
            'tables': tables
        }
    
    def _detect_column_layout(self, elements: List, page_no: int) -> Dict[str, Any]:
        """
        Intelligent column detection based on content analysis.
        
        Algorithm:
        1. Collect horizontal positions of all text/table elements
        2. Find natural vertical gaps (white space) that span the page height
        3. Identify column boundaries
        4. Classify layout: single-column, two-column, multi-column
        
        NOT a mechanical left/right split at page center!
        
        Args:
            elements: List of elements on page
            page_no: Page number
        
        Returns:
            Layout information dictionary
        """
        if not elements:
            return {'type': 'empty', 'columns': [], 'gaps': []}
        
        # Collect bounding boxes
        bboxes = []
        page_width = 0
        
        for elem in elements:
            if hasattr(elem, 'prov') and elem.prov:
                bbox = elem.prov[0].bbox
                bboxes.append({
                    'left': bbox.l,
                    'right': bbox.r,
                    'top': bbox.t,
                    'bottom': bbox.b,
                    'type': elem.label
                })
                page_width = max(page_width, bbox.r)
        
        if not bboxes:
            return {'type': 'empty', 'columns': [], 'gaps': []}
        
        # Find vertical gaps (potential column boundaries)
        gaps = self._find_vertical_gaps(bboxes, page_width)
        
        # Determine layout type based on gaps
        if len(gaps) == 0:
            layout_type = 'single-column'
            columns = [{'left': 0, 'right': page_width}]
        elif len(gaps) == 1:
            layout_type = 'two-column'
            gap_pos = gaps[0]
            columns = [
                {'left': 0, 'right': gap_pos},
                {'left': gap_pos, 'right': page_width}
            ]
        else:
            layout_type = 'multi-column'
            columns = self._define_columns_from_gaps(gaps, page_width)
        
        return {
            'type': layout_type,
            'columns': columns,
            'gaps': gaps
        }
    
    def _find_vertical_gaps(self, bboxes: List[Dict], page_width: float) -> List[float]:
        """
        Find vertical gaps that could be column boundaries.
        
        A gap is a vertical line where no content exists across most of the page height.
        
        Args:
            bboxes: List of bounding boxes
            page_width: Page width
        
        Returns:
            List of x-coordinates representing gap centers
        """
        # Create a histogram of horizontal coverage
        # Divide page into 100 vertical slices
        num_slices = 100
        slice_width = page_width / num_slices
        coverage = [0] * num_slices
        
        # Mark slices that have content
        for bbox in bboxes:
            left_slice = int(bbox['left'] / slice_width)
            right_slice = int(bbox['right'] / slice_width)
            
            for i in range(left_slice, min(right_slice + 1, num_slices)):
                coverage[i] += 1
        
        # Find gaps (slices with low coverage)
        threshold = max(coverage) * 0.1  # Gap if less than 10% of max coverage
        gaps = []
        in_gap = False
        gap_start = 0
        
        for i, count in enumerate(coverage):
            if count < threshold:
                if not in_gap:
                    gap_start = i
                    in_gap = True
            else:
                if in_gap:
                    # End of gap
                    gap_center = ((gap_start + i) / 2) * slice_width
                    gap_width = (i - gap_start) * slice_width
                    
                    # Only consider significant gaps (at least 5% of page width)
                    if gap_width > page_width * 0.05:
                        gaps.append(gap_center)
                    
                    in_gap = False
        
        return gaps
    
    def _define_columns_from_gaps(self, gaps: List[float], page_width: float) -> List[Dict[str, float]]:
        """Define column boundaries from detected gaps."""
        columns = []
        
        # First column: from left edge to first gap
        columns.append({'left': 0, 'right': gaps[0]})
        
        # Middle columns: between gaps
        for i in range(len(gaps) - 1):
            columns.append({'left': gaps[i], 'right': gaps[i + 1]})
        
        # Last column: from last gap to right edge
        columns.append({'left': gaps[-1], 'right': page_width})
        
        return columns
    
    def _group_elements_by_column(self, elements: List, layout_info: Dict) -> List[List]:
        """
        Group elements by column based on their bounding boxes.
        
        Args:
            elements: List of elements
            layout_info: Layout information with column boundaries
        
        Returns:
            List of element lists (one per column)
        """
        columns = layout_info['columns']
        grouped = [[] for _ in columns]
        
        for elem in elements:
            if not hasattr(elem, 'prov') or not elem.prov:
                continue
            
            bbox = elem.prov[0].bbox
            elem_center = (bbox.l + bbox.r) / 2
            
            # Find which column this element belongs to
            for col_idx, col in enumerate(columns):
                if col['left'] <= elem_center <= col['right']:
                    grouped[col_idx].append(elem)
                    break
        
        return grouped
    
    def _determine_reading_order(self, columns: List[List], layout_info: Dict) -> List:
        """
        Determine reading order for elements.
        
        For multi-column layouts:
        1. Sort elements within each column by vertical position (top to bottom)
        2. Interleave columns in reading order (left to right)
        
        Args:
            columns: Elements grouped by column
            layout_info: Layout information
        
        Returns:
            Ordered list of elements
        """
        # Sort elements within each column by vertical position
        for col in columns:
            col.sort(key=lambda elem: (
                elem.prov[0].bbox.t if hasattr(elem, 'prov') and elem.prov else 0
            ))
        
        # For now, simple left-to-right, top-to-bottom
        # Could be enhanced with more sophisticated logic
        ordered = []
        for col in columns:
            ordered.extend(col)
        
        return ordered
    
    def _extract_table_structure(self, table_elem, page_no: int) -> Optional[EnhancedFinancialTable]:
        """
        Extract complete table structure with:
        - Multi-level column headers
        - Row headers with hierarchy
        - Data cells with type preservation
        - Footnote linking
        
        Args:
            table_elem: Docling table element
            page_no: Page number
        
        Returns:
            EnhancedFinancialTable or None
        """
        try:
            # Get table caption/title
            caption = table_elem.caption if hasattr(table_elem, 'caption') else f"Table on page {page_no}"
            
            # Get table data
            table_data = table_elem.data if hasattr(table_elem, 'data') else None
            if not table_data:
                return None
            
            # Extract column headers
            column_headers = self._extract_column_headers(table_data)
            
            # Extract row headers
            row_headers = self._extract_row_headers(table_data)
            
            # Extract data cells
            data_cells = self._extract_data_cells(table_data, column_headers, row_headers)
            
            # Extract footnotes
            footnotes = self._extract_footnotes(table_elem, data_cells)
            
            # Extract periods from column headers
            periods = self._extract_periods(column_headers)
            
            # Classify table type
            table_type = self._classify_table_type(caption)
            
            # Canonicalize title
            canonical_title = self._canonicalize_title(caption)
            
            return EnhancedFinancialTable(
                table_id=str(uuid.uuid4()),
                source_document=self.filename,
                document_metadata={
                    'filename': self.filename,
                    'page_no': page_no
                },
                table_type=table_type,
                canonical_title=canonical_title,
                original_title=caption,
                periods=periods,
                column_headers=column_headers,
                row_headers=row_headers,
                data_cells=data_cells,
                footnotes=footnotes,
                metadata={
                    'page_no': page_no,
                    'num_rows': len(row_headers),
                    'num_columns': len(column_headers)
                }
            )
        except Exception as e:
            print(f"Error extracting table structure: {e}")
            return None
    
    def _extract_column_headers(self, table_data) -> List[ColumnHeader]:
        """Extract column headers with multi-level support."""
        column_headers = []
        
        # Docling provides table data - need to identify header rows
        # Typically first 1-2 rows are headers
        if not hasattr(table_data, 'table_cells') or not table_data.table_cells:
            return column_headers
        
        # For simplicity, treat first row as headers
        # TODO: Enhance to detect multi-level headers
        first_row = table_data.table_cells[0] if table_data.table_cells else []
        
        for col_idx, cell in enumerate(first_row):
            text = cell.text if hasattr(cell, 'text') else str(cell)
            
            # Detect units in header
            units = self.unit_converter.detect_unit(text)
            
            column_headers.append(ColumnHeader(
                row_index=0,
                column_index=col_idx,
                text=text.strip(),
                column_span=1,
                parent_header=None,
                units=units
            ))
        
        return column_headers
    
    def _extract_row_headers(self, table_data) -> List[RowHeader]:
        """
        Extract row headers (stub column) with indentation hierarchy.
        
        Critical for financial tables!
        """
        row_headers = []
        
        if not hasattr(table_data, 'table_cells') or not table_data.table_cells:
            return row_headers
        
        # Skip first row (headers), process data rows
        for row_idx, row in enumerate(table_data.table_cells[1:], 1):
            if not row:
                continue
            
            # First column is typically the stub column (row header)
            stub_cell = row[0]
            text = stub_cell.text if hasattr(stub_cell, 'text') else str(stub_cell)
            text = text.strip()
            
            # Detect indentation level
            indent_level = self._detect_indent_level(text)
            
            # Determine parent row
            parent_row = self._find_parent_row(row_headers, indent_level)
            
            # Canonicalize label
            canonical, confidence = self.label_normalizer.canonicalize(text)
            
            # Detect if subtotal or total row
            is_subtotal = 'subtotal' in text.lower()
            is_total = 'total' in text.lower() and not is_subtotal
            
            row_headers.append(RowHeader(
                row_index=row_idx,
                text=text,
                indent_level=indent_level,
                parent_row=parent_row,
                canonical_label=canonical if confidence > 0.7 else None,
                is_subtotal=is_subtotal,
                is_total=is_total
            ))
        
        return row_headers
    
    def _detect_indent_level(self, text: str) -> int:
        """Detect indentation level from text."""
        # Count leading spaces
        leading_spaces = len(text) - len(text.lstrip())
        
        # Rough heuristic: 2-4 spaces per indent level
        indent_level = leading_spaces // 3
        
        return min(indent_level, 3)  # Cap at level 3
    
    def _find_parent_row(self, row_headers: List[RowHeader], indent_level: int) -> Optional[str]:
        """Find parent row for current indent level."""
        if indent_level == 0 or not row_headers:
            return None
        
        # Find most recent row with lower indent level
        for row_header in reversed(row_headers):
            if row_header.indent_level < indent_level:
                return row_header.text
        
        return None
    
    def _extract_data_cells(
        self,
        table_data,
        column_headers: List[ColumnHeader],
        row_headers: List[RowHeader]
    ) -> List[DataCell]:
        """
        Extract data cells with full metadata:
        - Link to row header and column header
        - Parse data type
        - Detect units
        - Preserve alignment
        - Find footnote markers
        """
        data_cells = []
        
        if not hasattr(table_data, 'table_cells') or not table_data.table_cells:
            return data_cells
        
        # Process data rows (skip header row)
        for row_idx, row in enumerate(table_data.table_cells[1:], 1):
            if row_idx >= len(row_headers):
                break
            
            row_header = row_headers[row_idx - 1].text
            
            # Process data columns (skip stub column)
            for col_idx, cell in enumerate(row[1:], 1):
                if col_idx >= len(column_headers):
                    break
                
                column_header = column_headers[col_idx].text
                
                # Get cell text
                raw_text = cell.text if hasattr(cell, 'text') else str(cell)
                raw_text = raw_text.strip()
                
                # Parse value and detect type
                parsed_value, data_type = self._parse_cell_value(raw_text)
                
                # Detect units
                units = column_headers[col_idx].units
                
                # Convert to base value if numeric
                base_value = None
                display_value = raw_text
                original_unit = None
                
                if parsed_value is not None and units:
                    base_value, base_unit, display_value = self.unit_converter.convert_to_base(
                        parsed_value, units
                    )
                    original_unit = units
                
                # Find footnote markers
                footnote_refs = self._find_footnote_markers(raw_text)
                
                data_cells.append(DataCell(
                    row=row_idx,
                    column=col_idx,
                    row_header=row_header,
                    column_header=column_header,
                    raw_text=raw_text,
                    parsed_value=parsed_value,
                    data_type=data_type,
                    units=units,
                    original_unit=original_unit,
                    base_value=base_value,
                    display_value=display_value,
                    alignment=None,  # TODO: Extract from Docling if available
                    footnote_refs=footnote_refs
                ))
        
        return data_cells
    
    def _parse_cell_value(self, text: str) -> Tuple[Optional[float], str]:
        """
        Parse cell value and determine data type.
        
        Returns: (parsed_value, data_type)
        """
        text_clean = text.replace('$', '').replace(',', '').replace('(', '-').replace(')', '').strip()
        
        # Check for percentage
        if '%' in text:
            try:
                value = float(text_clean.replace('%', ''))
                return value, 'percentage'
            except:
                return None, 'text'
        
        # Check for currency
        if '$' in text:
            try:
                value = float(text_clean)
                return value, 'currency'
            except:
                return None, 'text'
        
        # Check for number
        try:
            value = float(text_clean)
            return value, 'number'
        except:
            # Check if it's a date
            if re.search(r'\d{1,2}/\d{1,2}/\d{2,4}', text):
                return None, 'date'
            
            return None, 'text'
    
    def _find_footnote_markers(self, text: str) -> List[str]:
        """Find footnote markers in text."""
        markers = []
        
        # Look for superscript numbers or symbols
        # Pattern: ¹, ², ³, (1), (2), *, **
        patterns = [
            r'[¹²³⁴⁵⁶⁷⁸⁹]',
            r'\((\d+)\)',
            r'(\*+)'
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, text)
            markers.extend(matches)
        
        return markers
    
    def _extract_footnotes(self, table_elem, data_cells: List[DataCell]) -> List[Footnote]:
        """Extract and link footnotes."""
        footnotes = []
        
        # TODO: Extract footnote text from below table
        # This requires analyzing text elements near the table
        # For now, return empty list
        
        return footnotes
    
    def _extract_periods(self, column_headers: List[ColumnHeader]) -> List[Period]:
        """Extract periods from column headers."""
        periods = []
        
        for header in column_headers:
            period = self.period_parser.parse_period(header.text)
            if period and period not in periods:
                periods.append(period)
        
        return periods
    
    def _classify_table_type(self, title: str) -> str:
        """Classify table type from title."""
        title_lower = title.lower()
        
        if 'balance sheet' in title_lower or 'financial condition' in title_lower:
            return 'balance_sheet'
        elif 'income statement' in title_lower or 'earnings' in title_lower:
            return 'income_statement'
        elif 'cash flow' in title_lower:
            return 'cash_flow_statement'
        elif 'equity' in title_lower:
            return 'equity_statement'
        elif 'segment' in title_lower:
            return 'segment_information'
        elif 'fair value' in title_lower:
            return 'fair_value'
        elif 'derivative' in title_lower:
            return 'derivatives'
        else:
            return 'other'
    
    def _canonicalize_title(self, title: str) -> str:
        """Create canonical title."""
        return title.lower().replace(' ', '_').replace(',', '').replace('.', '')
    
    def _merge_multi_page_tables(self, tables: List[EnhancedFinancialTable]) -> List[EnhancedFinancialTable]:
        """
        Detect and merge tables that span multiple pages.
        
        Heuristics:
        - Same or similar title on consecutive pages
        - Matching column headers
        - "Continued" indicators
        """
        if len(tables) <= 1:
            return tables
        
        merged = []
        skip_indices = set()
        
        for i, table in enumerate(tables):
            if i in skip_indices:
                continue
            
            # Look for continuation on next page
            if i + 1 < len(tables):
                next_table = tables[i + 1]
                
                if self._is_continuation(table, next_table):
                    # Merge tables
                    merged_table = self._merge_tables(table, next_table)
                    merged.append(merged_table)
                    skip_indices.add(i + 1)
                    continue
            
            merged.append(table)
        
        return merged
    
    def _is_continuation(self, table1: EnhancedFinancialTable, table2: EnhancedFinancialTable) -> bool:
        """Check if table2 is a continuation of table1."""
        # Check if on consecutive pages
        page1 = table1.metadata.get('page_no', 0)
        page2 = table2.metadata.get('page_no', 0)
        
        if page2 != page1 + 1:
            return False
        
        # Check for "continued" in title
        if 'continued' in table2.original_title.lower():
            return True
        
        # Check if titles are similar
        if table1.canonical_title == table2.canonical_title:
            return True
        
        # Check if column headers match
        if len(table1.column_headers) == len(table2.column_headers):
            headers_match = all(
                h1.text == h2.text
                for h1, h2 in zip(table1.column_headers, table2.column_headers)
            )
            if headers_match:
                return True
        
        return False
    
    def _merge_tables(
        self,
        table1: EnhancedFinancialTable,
        table2: EnhancedFinancialTable
    ) -> EnhancedFinancialTable:
        """Merge two continuation tables."""
        # Combine row headers and data cells
        merged_row_headers = table1.row_headers + table2.row_headers
        merged_data_cells = table1.data_cells + table2.data_cells
        merged_footnotes = table1.footnotes + table2.footnotes
        
        # Update row indices for table2 rows
        offset = len(table1.row_headers)
        for row_header in merged_row_headers[offset:]:
            row_header.row_index += offset
        
        for data_cell in merged_data_cells:
            if data_cell.row >= offset:
                data_cell.row += offset
        
        return EnhancedFinancialTable(
            table_id=table1.table_id,
            source_document=table1.source_document,
            document_metadata=table1.document_metadata,
            table_type=table1.table_type,
            canonical_title=table1.canonical_title,
            original_title=table1.original_title,
            periods=table1.periods,
            column_headers=table1.column_headers,
            row_headers=merged_row_headers,
            data_cells=merged_data_cells,
            footnotes=merged_footnotes,
            metadata={
                'page_no': f"{table1.metadata['page_no']}-{table2.metadata['page_no']}",
                'num_rows': len(merged_row_headers),
                'num_columns': len(table1.column_headers),
                'merged': True
            }
        )

