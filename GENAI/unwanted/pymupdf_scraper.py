"""
Modern PDF scraper using PyMuPDF's native table detection.
Superior to pdfplumber for complex financial documents.
"""

import fitz  # PyMuPDF
import pandas as pd
from typing import List, Optional, Dict, Any
import re

from models.schemas import FinancialTable


class PyMuPDFScraper:
    """
    Modern PDF scraper using PyMuPDF's native table detection.
    
    Advantages over pdfplumber:
    - 10-100x faster
    - Better table structure detection
    - Handles complex multi-column layouts
    - More accurate for financial documents
    """
    
    def __init__(self, pdf_path: str):
        self.pdf_path = pdf_path
        self.filename = pdf_path.split('/')[-1]
        self.doc = None
        
    def __enter__(self):
        self.doc = fitz.open(self.pdf_path)
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.doc:
            self.doc.close()
    
    def extract_all_tables(self, pages: Optional[List[int]] = None) -> List[FinancialTable]:
        """Extract all tables from PDF using PyMuPDF's table detection."""
        if not self.doc:
            self.doc = fitz.open(self.pdf_path)
        
        extracted_tables = []
        
        if pages is None:
            pages_to_process = range(len(self.doc))
        else:
            pages_to_process = pages
        
        for page_num in pages_to_process:
            page = self.doc[page_num]
            tables = self._extract_tables_from_page(page, page_num + 1)  # 1-indexed
            extracted_tables.extend(tables)
        
        return extracted_tables
    
    def _extract_tables_from_page(self, page, page_number: int) -> List[FinancialTable]:
        """Extract tables from a single page using PyMuPDF's find_tables()."""
        financial_tables = []
        
        # Find tables using PyMuPDF's table detection
        tables = page.find_tables()
        
        if not tables or not tables.tables:
            return financial_tables
        
        for i, table in enumerate(tables.tables):
            try:
                # Extract table data
                table_data = table.extract()
                
                if not table_data or len(table_data) < 2:
                    continue
                
                # Convert to DataFrame
                df = pd.DataFrame(table_data)
                
                # Clean the dataframe
                df_clean = self._clean_dataframe(df)
                
                if df_clean.empty or len(df_clean) < 1:
                    continue
                
                # Extract title
                title = self._extract_title(page, table.bbox, page_number)
                
                if not title:
                    title = f"Table_{i+1}"
                
                # Get headers and rows
                headers = df_clean.columns.tolist()
                rows = df_clean.values.tolist()
                
                # Create FinancialTable object
                ft = FinancialTable(
                    title=title,
                    page_number=page_number,
                    headers=[str(h) for h in headers],
                    rows=rows
                )
                financial_tables.append(ft)
                
            except Exception as e:
                print(f"Error extracting table {i} on page {page_number}: {e}")
                continue
        
        return financial_tables
    
    def _extract_title(self, page, bbox: tuple, page_number: int) -> str:
        """Extract table title from text above the table."""
        x0, y0, x1, y1 = bbox
        
        # Define search area above the table
        search_rect = fitz.Rect(
            x0,
            max(0, y0 - 60),  # Look 60 points above
            x1,
            y0
        )
        
        # Extract text from search area
        text_above = page.get_text("text", clip=search_rect)
        
        if not text_above:
            return ""
        
        # Process lines
        lines = [l.strip() for l in text_above.split('\n') if l.strip()]
        
        # Filter and find best title candidate
        for line in reversed(lines):  # Start from closest to table
            # Skip noise
            if any(noise in line.lower() for noise in [
                'table of contents',
                'notes to',
                'unaudited',
                'dollars in millions',
                'page ',
                'form 10-'
            ]):
                continue
            
            # Skip lines that are just numbers or too short
            if len(line) < 10 or line.replace(',', '').replace('.', '').replace('$', '').replace(' ', '').isdigit():
                continue
            
            # Skip lines with mostly dollar signs
            if line.count('$') > 3:
                continue
            
            # This looks like a good title
            if len(line) < 200:  # Not too long
                # Clean up superscripts and special characters
                clean_title = re.sub(r'[¹²³⁴⁵⁶⁷⁸⁹⁰]', '', line)
                return clean_title.strip()
        
        return ""
    
    def _clean_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """Clean extracted dataframe."""
        # Drop completely empty rows and columns
        df = df.dropna(axis=0, how='all')
        df = df.dropna(axis=1, how='all')
        
        if df.empty:
            return df
        
        # Remove rows with "Table of Contents" or similar noise
        if len(df) > 0 and len(df.columns) > 0:
            first_col = df.iloc[:, 0].astype(str).str.lower()
            mask = ~first_col.str.contains('table of contents|notes to consolidated|unaudited', na=False, regex=True)
            df = df[mask]
        
        if df.empty:
            return df
        
        # Handle multi-row headers
        if len(df) > 1:
            first_row = df.iloc[0]
            # Check if first row is mostly empty (likely part of header)
            empty_count = first_row.isna().sum() + (first_row.astype(str) == '').sum() + (first_row.astype(str) == 'None').sum()
            
            if empty_count > len(df.columns) / 2:
                # Combine first two rows as header
                if len(df) > 1:
                    second_row = df.iloc[1]
                    new_header = []
                    for h1, h2 in zip(first_row, second_row):
                        h1_str = str(h1) if pd.notna(h1) and str(h1) not in ['', 'None'] else ''
                        h2_str = str(h2) if pd.notna(h2) and str(h2) not in ['', 'None'] else ''
                        combined = f"{h1_str} {h2_str}".strip()
                        new_header.append(combined if combined else f"Col_{len(new_header)}")
                    df = df[2:]
                    df.columns = new_header
            else:
                # Use first row as header
                df.columns = df.iloc[0]
                df = df[1:]
        
        # Clean column names
        df.columns = df.columns.astype(str).str.strip()
        df = df.reset_index(drop=True)
        
        # Remove duplicate headers that appear in data
        if len(df) > 0:
            try:
                header_str = '|'.join(df.columns.astype(str).str.lower())
                first_row_str = '|'.join(df.iloc[0].astype(str).str.lower())
                if header_str == first_row_str:
                    df = df[1:]
            except:
                pass
        
        return df


# Convenience function for quick extraction
def extract_tables_pymupdf(pdf_path: str, pages: Optional[List[int]] = None) -> List[FinancialTable]:
    """Extract tables using PyMuPDF scraper."""
    with PyMuPDFScraper(pdf_path) as scraper:
        return scraper.extract_all_tables(pages=pages)
