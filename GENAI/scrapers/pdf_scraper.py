"""Enhanced PDF scraper with 2-column layout support."""

import pdfplumber
import pandas as pd
from typing import List, Optional, Dict, Any, Tuple
from operator import itemgetter
import re

from models.schemas import FinancialTable, TableMetadata


class EnhancedPDFScraper:
    """
    Enhanced PDF scraper that handles:
    - 2-column layouts (common in financial reports)
    - Table extraction with proper structure
    - Title extraction using block-based layout analysis
    - Fragmented tables across columns
    - Special HTML extraction for complex tables
    """
    
    # Configuration for specific tables that need special handling
    TABLE_CONFIGS = {
        "Difference Between Contractual Principal and Fair Value": {
            "strategy": "html",
            "bbox_width": 310,
            "col_tolerance": 38,
            "filter_footnotes": True,
            "stop_titles": [
                "Fair Value Loans",
                "Fair Values"
            ]
        }
    }
    
    def __init__(self, pdf_path: str):
        self.pdf_path = pdf_path
        self.filename = pdf_path.split('/')[-1]
        
    def extract_all_tables(self, pages: Optional[List[int]] = None) -> List[FinancialTable]:
        """Extract all tables from the PDF."""
        extracted_tables = []
        
        with pdfplumber.open(self.pdf_path) as pdf:
            if pages is None:
                pages_to_process = pdf.pages
            else:
                pages_to_process = [pdf.pages[i] for i in pages if 0 <= i < len(pdf.pages)]
            
            for page in pages_to_process:
                tables = self._extract_tables_from_page(page)
                extracted_tables.extend(tables)
        
        return extracted_tables
    
    def _extract_tables_from_page(self, page) -> List[FinancialTable]:
        """Extract tables from a single page with 2-column layout support."""
        financial_tables = []
        
        # Configure table detection settings
        settings = {
            "vertical_strategy": "text",
            "horizontal_strategy": "lines",
            "intersection_y_tolerance": 10,
            "text_x_tolerance": 5,
        }
        
        page_tables = page.find_tables(settings)
        
        # Sort tables by column (Inverse N style) then vertical position
        # This handles 2-column layouts properly
        midpoint = page.width / 2
        
        def sort_key(t):
            x0, y0, x1, y1 = t.bbox
            center_x = (x0 + x1) / 2
            # Left column (0) or Right column (1)
            col_index = 1 if center_x > midpoint else 0
            return (col_index, y0)
        
        page_tables.sort(key=sort_key)
        
        for i, table in enumerate(page_tables):
            bbox = table.bbox
            
            # Filter out false positives
            if self._is_false_positive(page, bbox):
                continue
            
            # Extract title
            title = self._extract_title(page, bbox, page_tables, i)
            
            # Check if this table needs special handling
            config = None
            for key, cfg in self.TABLE_CONFIGS.items():
                if key in title:
                    config = cfg
                    print(f"Applying special configuration for table: {title}")
                    break
            
            # Use HTML extraction for complex tables
            if config and config.get("strategy") == "html":
                width = config.get("bbox_width", page.width)
                special_bbox = (0, bbox[1], width, page.height)
                
                result = self._extract_via_html(
                    page,
                    special_bbox,
                    col_tolerance=config.get("col_tolerance", 10),
                    filter_footnotes=config.get("filter_footnotes", False),
                    stop_titles=config.get("stop_titles", [])
                )
                
                if result and len(result) == 2:
                    rows, headers = result
                    if rows:
                        try:
                            ft = FinancialTable(
                                title=title,
                                page_number=page.page_number,
                                headers=[str(h) for h in headers],
                                rows=rows
                            )
                            financial_tables.append(ft)
                            continue
                        except Exception as e:
                            print(f"HTML extraction validation failed: {e}")
            
            # Standard extraction for regular tables
            data = table.extract()
            if not data:
                continue
            
            df = pd.DataFrame(data)
            df_clean = self._clean_dataframe(df)
            
            if df_clean.empty:
                continue
            
            headers = df_clean.columns.tolist()
            rows = df_clean.values.tolist()
            
            if not title:
                title = f"Table_{i+1}"
            
            try:
                ft = FinancialTable(
                    title=title,
                    page_number=page.page_number,
                    headers=[str(h) for h in headers],
                    rows=rows
                )
                financial_tables.append(ft)
            except Exception as e:
                print(f"Skipping table on page {page.page_number}: {e}")
        
        return financial_tables
    
    def _is_false_positive(self, page, bbox) -> bool:
        """Filter out false positive table detections."""
        x0, y0, x1, y1 = bbox
        width = x1 - x0
        height = y1 - y0
        
        # Filter very small tables
        if width < 50 or height < 30:
            return True
        
        # Filter header/footer tables
        if y0 < 50 and height > 600:
            return True
        
        # Content-based filtering
        try:
            raw_text = page.within_bbox(bbox).extract_text()
            if raw_text:
                lower_text = raw_text.lower()
                if "table of contents" in lower_text:
                    return True
                if "notes to consolidated financial statements" in lower_text and width < 200:
                    return True
        except Exception:
            pass
        
        return False
    
    def _extract_title(self, page, bbox, all_tables, current_index) -> str:
        """
        Extract table title using Block-Based Layout Analysis.
        Handles 2-column layouts by analyzing text in the same column as the table.
        """
        x0, y0, x1, y1 = bbox
        
        # Get words with font information
        words = page.extract_words(extra_attrs=["fontname", "size"])
        if not words:
            return ""
        
        # Sort by vertical position
        words.sort(key=lambda w: (w['top'], w['x0']))
        
        # Determine which column the table is in
        midpoint = page.width / 2
        table_center = (x0 + x1) / 2
        
        if table_center < midpoint:
            # Table in left column - only consider left column words
            col_words = [w for w in words if w['x0'] < midpoint]
        else:
            # Table in right column - only consider right column words
            col_words = [w for w in words if w['x0'] >= midpoint]
        
        if not col_words:
            return ""
        
        # Cluster words into lines
        lines = self._cluster_into_lines(col_words)
        
        # Cluster lines into blocks
        blocks = self._cluster_into_blocks(lines)
        
        # Find nearest block above table
        title = self._find_nearest_title_block(blocks, bbox)
        
        return title
    
    def _cluster_into_lines(self, words: List[Dict]) -> List[List[Dict]]:
        """Cluster words into lines based on vertical position."""
        lines = []
        current_line = []
        last_top = -1
        
        for w in words:
            if last_top == -1 or abs(w['top'] - last_top) < 5:
                current_line.append(w)
            else:
                if current_line:
                    lines.append(current_line)
                current_line = [w]
            last_top = w['top']
        
        if current_line:
            lines.append(current_line)
        
        return lines
    
    def _cluster_into_blocks(self, lines: List[List[Dict]]) -> List[List[List[Dict]]]:
        """Cluster lines into blocks (paragraphs) based on spacing."""
        blocks = []
        current_block_lines = []
        last_line_bottom = -1
        
        for line in lines:
            line_top = min(w['top'] for w in line)
            line_bottom = max(w['bottom'] for w in line)
            
            if last_line_bottom == -1:
                current_block_lines.append(line)
            else:
                gap = line_top - last_line_bottom
                if gap > 10:  # New block threshold
                    if current_block_lines:
                        blocks.append(current_block_lines)
                    current_block_lines = [line]
                else:
                    current_block_lines.append(line)
            
            last_line_bottom = line_bottom
        
        if current_block_lines:
            blocks.append(current_block_lines)
        
        return blocks
    
    def _find_nearest_title_block(self, blocks: List[List[List[Dict]]], bbox: Tuple) -> str:
        """Find the nearest text block above the table that could be a title."""
        x0, y0, x1, y1 = bbox
        nearest_block = None
        min_dist = float('inf')
        
        for block_lines in blocks:
            # Calculate block bounds
            all_words = [w for line in block_lines for w in line]
            b_y1 = max(w['bottom'] for w in all_words)
            b_x0 = min(w['x0'] for w in all_words)
            b_x1 = max(w['x1'] for w in all_words)
            
            # Check if block is above table
            if b_y1 <= y0 + 5:  # Tolerance
                dist = y0 - b_y1
                
                # Check horizontal overlap
                overlap = max(0, min(x1, b_x1) - max(x0, b_x0))
                if overlap > 0:
                    if dist < min_dist:
                        min_dist = dist
                        nearest_block = block_lines
        
        if nearest_block and min_dist < 100:  # Max distance for a title
            return self._process_title_block(nearest_block)
        
        return ""
    
    def _process_title_block(self, block_lines: List[List[Dict]]) -> str:
        """Process a title block, filtering out noise."""
        valid_lines = []
        
        for line in block_lines:
            line_text = " ".join([w['text'] for w in line])
            lower_line = line_text.lower()
            
            # Filter noise
            if any(noise in lower_line for noise in [
                "table of contents",
                "notes to",
                "unaudited",
                "dollars in"
            ]):
                continue
            
            if lower_line.startswith(("page", "at ", "as of ")):
                continue
            
            if "$" in line_text:
                continue
            
            valid_lines.append(line_text)
        
        return " ".join(valid_lines).strip()
    
    def _clean_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """Clean extracted dataframe."""
        # Replace newlines
        df = df.replace(r'\\n', ' ', regex=True)
        
        # Drop empty rows/columns
        df = df.dropna(axis=0, how='all')
        df = df.dropna(axis=1, how='all')
        
        if df.empty:
            return df
        
        # Filter out noise rows
        first_col = df.iloc[:, 0].astype(str).str.lower()
        mask = ~first_col.str.contains('table of conten') & \
               ~first_col.str.contains('notes t') & \
               ~first_col.str.contains('unaudited')
        df = df[mask]
        
        if df.empty:
            return df
        
        # Handle multi-row headers
        first_row = df.iloc[0]
        empty_count = first_row.isna().sum() + (first_row == '').sum() + (first_row == 'None').sum()
        
        if len(df) > 1 and empty_count > len(df.columns) / 2:
            # Combine first two rows as header
            second_row = df.iloc[1]
            new_header = []
            for h1, h2 in zip(first_row, second_row):
                h1 = str(h1) if pd.notna(h1) and h1 != '' else ''
                h2 = str(h2) if pd.notna(h2) and h2 != '' else ''
                new_header.append(f"{h1} {h2}".strip())
            df = df[2:]
            df.columns = new_header
        else:
            # Use first row as header
            df.columns = df.iloc[0]
            df = df[1:]
        
        df.columns = df.columns.astype(str).str.strip()
        df = df.reset_index(drop=True)
        
        return df
    
    def _extract_via_html(self, page, bbox, col_tolerance=10, filter_footnotes=False, stop_titles=None):
        """Extract table using HTML parsing for complex multi-column tables."""
        try:
            import lxml  # noqa
        except ImportError:
            print("lxml not installed. Skipping HTML extraction.")
            return None
        
        words = page.within_bbox(bbox).extract_words()
        if not words:
            return None
        
        words.sort(key=itemgetter('top'))
        rows = []
        current_row = []
        last_top = -1
        row_tolerance = 5
        
        for word in words:
            if last_top == -1:
                current_row.append(word)
                last_top = word['top']
            else:
                if abs(word['top'] - last_top) <= row_tolerance:
                    current_row.append(word)
                else:
                    rows.append(current_row)
                    current_row = [word]
                    last_top = word['top']
        if current_row:
            rows.append(current_row)
        
        rows_of_cells = []
        all_cell_centers = []
        
        for row_words in rows:
            row_words.sort(key=itemgetter('x0'))
            full_text = " ".join([w['text'] for w in row_words])
            
            if stop_titles:
                should_stop = False
                for stop_title in stop_titles:
                    if stop_title in full_text:
                        should_stop = True
                        break
                if should_stop:
                    break
            
            if filter_footnotes:
                if full_text.strip().startswith(("1.", "2.", "3.", "4.", "5.", "6.")):
                    break
                if "The previous tables exclude" in full_text:
                    break
            
            row_cells = []
            if row_words:
                curr_cell_words = [row_words[0]]
                for w in row_words[1:]:
                    if w['x0'] - curr_cell_words[-1]['x1'] < 10:
                        curr_cell_words.append(w)
                    else:
                        row_cells.append(curr_cell_words)
                        curr_cell_words = [w]
                row_cells.append(curr_cell_words)
            
            rows_of_cells.append(row_cells)
            for cell in row_cells:
                center = (cell[0]['x0'] + cell[-1]['x1']) / 2
                all_cell_centers.append(center)
        
        all_cell_centers.sort()
        cols = []
        if all_cell_centers:
            curr_c = [all_cell_centers[0]]
            for c in all_cell_centers[1:]:
                if c - curr_c[-1] < col_tolerance:
                    curr_c.append(c)
                else:
                    cols.append(sum(curr_c)/len(curr_c))
                    curr_c = [c]
            cols.append(sum(curr_c)/len(curr_c))
        
        html = "<table border='1'>"
        for row_cells in rows_of_cells:
            html += "<tr>"
            final_row_cells = [""] * len(cols)
            for cell_words in row_cells:
                cell_text = " ".join([w['text'] for w in cell_words])
                cell_center = (cell_words[0]['x0'] + cell_words[-1]['x1']) / 2
                if cols:
                    closest_col_idx = min(range(len(cols)), key=lambda i: abs(cols[i] - cell_center))
                    if final_row_cells[closest_col_idx]:
                        final_row_cells[closest_col_idx] += " " + cell_text
                    else:
                        final_row_cells[closest_col_idx] = cell_text
            for cell in final_row_cells:
                html += f"<td>{cell}</td>"
            html += "</tr>"
        html += "</table>"
        
        try:
            dfs = pd.read_html(html)
            if dfs:
                return dfs[0].values.tolist(), dfs[0].columns.tolist()
        except Exception as e:
            print(f"HTML parsing failed: {e}")
        
        return None
