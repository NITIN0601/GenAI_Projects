"""
PDF to Markdown converter using pymupdf4llm.
Simpler and more reliable than marker-pdf.
"""

import pymupdf4llm
from pathlib import Path
from typing import List, Optional
from bs4 import BeautifulSoup
import pandas as pd
import re

from models.schemas import FinancialTable


class PyMuPDF4LLMScraper:
    """
    Convert PDF to Markdown using pymupdf4llm, then extract tables.
    
    Advantages:
    - Simple, reliable
    - Tables as Markdown tables (can be converted to HTML)
    - Fast
    - No complex dependencies
    """
    
    def __init__(self, pdf_path: str):
        self.pdf_path = pdf_path
        self.filename = Path(pdf_path).name
        self.markdown_content = None
        
    def convert_to_markdown(self) -> str:
        """Convert PDF to Markdown using pymupdf4llm."""
        try:
            # Convert PDF to Markdown
            md_text = pymupdf4llm.to_markdown(self.pdf_path)
            self.markdown_content = md_text
            return md_text
        except Exception as e:
            print(f"Conversion error: {e}")
            return None
    
    def extract_all_tables(self, pages: Optional[List[int]] = None) -> List[FinancialTable]:
        """Extract tables from Markdown content."""
        if not self.markdown_content:
            self.convert_to_markdown()
        
        if not self.markdown_content:
            return []
        
        return self._extract_tables_from_markdown()
    
    def _extract_tables_from_markdown(self) -> List[FinancialTable]:
        """Extract Markdown tables from content."""
        financial_tables = []
        
        # Split by pages (pymupdf4llm includes page markers)
        pages = self._split_by_pages()
        
        for page_num, page_content in enumerate(pages, 1):
            # Find Markdown tables (lines starting with |)
            tables = self._find_markdown_tables(page_content)
            
            for i, (title, table_lines) in enumerate(tables):
                try:
                    # Convert Markdown table to DataFrame
                    df = self._markdown_table_to_dataframe(table_lines)
                    
                    if df is None or df.empty or len(df) < 1:
                        continue
                    
                    # Clean DataFrame
                    df_clean = self._clean_dataframe(df)
                    
                    if df_clean.empty:
                        continue
                    
                    if not title:
                        title = f"Table_{i+1}"
                    
                    # Get headers and rows
                    headers = df_clean.columns.tolist()
                    rows = df_clean.values.tolist()
                    
                    # Create FinancialTable
                    ft = FinancialTable(
                        title=title,
                        page_number=page_num,
                        headers=[str(h) for h in headers],
                        rows=rows
                    )
                    financial_tables.append(ft)
                    
                except Exception as e:
                    print(f"Error extracting table on page {page_num}: {e}")
                    continue
        
        return financial_tables
    
    def _split_by_pages(self) -> List[str]:
        """Split markdown by pages."""
        # pymupdf4llm uses -----\n\n as page separator
        if '-----' in self.markdown_content:
            pages = self.markdown_content.split('-----')
            return [p.strip() for p in pages if p.strip()]
        else:
            return [self.markdown_content]
    
    def _find_markdown_tables(self, content: str) -> List[tuple]:
        """Find Markdown tables and their titles."""
        lines = content.split('\n')
        tables = []
        current_table = []
        title = ""
        
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            
            # Check if this is a table row
            if line.startswith('|') and '|' in line[1:]:
                if not current_table:
                    # Look for title in previous lines
                    title = self._find_title_before_table(lines, i)
                current_table.append(line)
            else:
                # End of table
                if current_table:
                    tables.append((title, current_table))
                    current_table = []
                    title = ""
            
            i += 1
        
        # Don't forget last table
        if current_table:
            tables.append((title, current_table))
        
        return tables
    
    def _find_title_before_table(self, lines: List[str], table_start: int) -> str:
        """Find title in lines before table."""
        # Look at previous 10 lines
        for i in range(max(0, table_start - 10), table_start):
            line = lines[i].strip()
            
            # Skip empty lines
            if not line:
                continue
            
            # Check for headers (##, ###, etc.)
            if line.startswith('#'):
                title = re.sub(r'^#+\s*', '', line)
                return title.strip()
            
            # Check for bold text
            if '**' in line:
                title = re.sub(r'\*\*', '', line)
                if len(title) > 10 and len(title) < 200:
                    return title.strip()
            
            # Regular text that could be a title
            if len(line) > 10 and len(line) < 200 and not line.startswith('|'):
                if not any(noise in line.lower() for noise in [
                    'table of contents', 'unaudited', 'page ', 'form 10-', '-----'
                ]):
                    return line.strip()
        
        return ""
    
    def _markdown_table_to_dataframe(self, table_lines: List[str]) -> Optional[pd.DataFrame]:
        """Convert Markdown table to DataFrame."""
        if not table_lines or len(table_lines) < 2:
            return None
        
        # Parse table
        rows = []
        for line in table_lines:
            # Skip separator lines (|---|---|)
            if re.match(r'^\|[\s\-:]+\|$', line):
                continue
            
            # Split by | and clean
            cells = [cell.strip() for cell in line.split('|')[1:-1]]  # Remove first/last empty
            if cells:
                rows.append(cells)
        
        if not rows or len(rows) < 2:
            return None
        
        # First row is header
        df = pd.DataFrame(rows[1:], columns=rows[0])
        return df
    
    def _clean_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """Clean extracted dataframe."""
        # Drop empty rows/columns
        df = df.dropna(axis=0, how='all')
        df = df.dropna(axis=1, how='all')
        
        if df.empty:
            return df
        
        # Remove noise rows
        if len(df) > 0:
            first_col = df.iloc[:, 0].astype(str).str.lower()
            mask = ~first_col.str.contains('table of contents|notes to|unaudited', na=False, regex=True)
            df = df[mask]
        
        df.columns = df.columns.astype(str).str.strip()
        df = df.reset_index(drop=True)
        
        return df


def extract_tables_pymupdf4llm(pdf_path: str) -> List[FinancialTable]:
    """Extract tables using pymupdf4llm."""
    scraper = PyMuPDF4LLMScraper(pdf_path)
    return scraper.extract_all_tables()
