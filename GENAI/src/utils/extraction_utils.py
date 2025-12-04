"""
Common utilities for PDF extraction and processing.

Consolidates duplicate code from multiple extraction modules.
"""

from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime
import hashlib
import re

from docling.document_converter import DocumentConverter
from docling_core.types.doc import DocItemLabel
from src.models.schemas import TableMetadata


class DoclingHelper:
    """Helper class for common Docling operations."""
    
    @staticmethod
    def convert_pdf(pdf_path: str) -> Any:
        """
        Convert PDF using Docling.
        
        Args:
            pdf_path: Path to PDF file
            
        Returns:
            Docling conversion result
        """
        converter = DocumentConverter()
        return converter.convert(pdf_path)
    
    @staticmethod
    def get_item_page(item) -> int:
        """
        Get page number for a Docling item.
        
        Args:
            item: Docling document item
            
        Returns:
            Page number (1-indexed)
        """
        if hasattr(item, 'prov') and item.prov:
            for p in item.prov:
                if hasattr(p, 'page_no'):
                    return p.page_no
        return 1
    
    @staticmethod
    def extract_tables(doc) -> list:
        """
        Extract all tables from Docling document.
        
        Args:
            doc: Docling document
            
        Returns:
            List of table items
        """
        tables = []
        for item_data in doc.iterate_items():
            # Handle both tuple and direct item formats
            if isinstance(item_data, tuple):
                item = item_data[0]
            else:
                item = item_data
            
            if hasattr(item, 'label') and item.label == DocItemLabel.TABLE:
                tables.append(item)
        
        return tables
    
    @staticmethod
    def extract_table_title(doc, table_item, table_index: int, page_no: int) -> str:
        """
        Extract meaningful table title from surrounding context.
        
        Priority:
        1. Table caption if available
        2. Preceding text item (section header) on same page (filtering out dates/units)
        3. Fallback to page-based name
        
        Args:
            doc: Docling document
            table_item: The table item
            table_index: Index of table in document
            page_no: Page number
            
        Returns:
            Extracted table title
        """
        def clean_title(text: str) -> str:
            """Clean footnotes and extra whitespace from title."""
            if not text:
                return ""
            
            # Clean footnotes
            # Trailing number: "Text 2"
            text = re.sub(r'\s+\d+\s*$', '', text)
            # Parenthesized: "Text (1)"
            text = re.sub(r'\s*\(\d+\)\s*$', '', text)
            
            return text.strip()[:100]

        def is_valid_title(text: str) -> bool:
            """Check if text is a valid title and not a date/period header."""
            text_lower = text.lower()
            invalid_patterns = [
                'three months ended', 'six months ended', 'nine months ended', 'twelve months ended',
                'year ended', 'quarter ended', 'at march', 'at december', 'at june', 'at september',
                '$ in millions', '$ in billions', 'unaudited', '(unaudited)',
                'rows 1-', 'rows 10-'
            ]
            
            if len(text) < 3:
                return False
                
            for pattern in invalid_patterns:
                if pattern in text_lower:
                    return False
            
            return True

        # Try to get caption first
        if hasattr(table_item, 'caption') and table_item.caption:
            caption = str(table_item.caption).strip()
            if caption and len(caption) > 3 and is_valid_title(caption):
                return clean_title(caption)
        
        # Look for preceding text item that could be the table title
        try:
            items_list = list(doc.iterate_items())
            preceding_texts = []
            
            for item_data in items_list:
                item = item_data[0] if isinstance(item_data, tuple) else item_data
                
                # Check if this is our table
                if item is table_item:
                    break
                
                # Get page number
                item_page = 1
                if hasattr(item, 'prov') and item.prov:
                    for p in item.prov:
                        if hasattr(p, 'page_no'):
                            item_page = p.page_no
                
                # Only consider items on same page or preceding page
                if item_page >= page_no - 1:
                    label = str(item.label) if hasattr(item, 'label') else ''
                    
                    # Look for section headers, titles, or text items
                    if 'SECTION' in label.upper() or 'TITLE' in label.upper() or 'TEXT' in label.upper():
                        if hasattr(item, 'text') and item.text:
                            text = str(item.text).strip()
                            # Filter out long paragraphs, keep short titles
                            if 5 < len(text) < 150 and not text.startswith('|'):
                                preceding_texts.append(text)
            
            # Iterate backwards to find first valid title
            if preceding_texts:
                for text in reversed(preceding_texts):
                    if is_valid_title(text):
                        title = text
                        # Clean up common prefixes
                        for prefix in ['Note ', 'NOTE ', 'Table ']:
                            if title.startswith(prefix):
                                title = title[len(prefix):].strip()
                                if title and title[0].isdigit():
                                    # Skip the number
                                    parts = title.split(' ', 1)
                                    if len(parts) > 1:
                                        title = parts[1].strip()
                        
                        if title and len(title) > 3:
                            return clean_title(title)
        except Exception:
            pass
        
        # Fallback: Table with page reference
        return f"Table {table_index + 1} (Page {page_no})"


class FootnoteExtractor:
    """
    Extract and clean footnote references from table content.
    
    Handles patterns like:
    - "Loans and other receivables 2" -> ("Loans and other receivables", ["2"])
    - "Total assets (1)(2)" -> ("Total assets", ["1", "2"])
    - "Net income¹²" -> ("Net income", ["1", "2"])
    """
    
    # Patterns for footnote references
    FOOTNOTE_PATTERNS = [
        r'\s+(\d+)\s*$',           # Trailing number: "Text 2"
        r'\s*\((\d+)\)\s*$',       # Parenthesized: "Text (1)"
        r'\s*\[(\d+)\]\s*$',       # Bracketed: "Text [1]"
        r'(\s+\d+)+\s*$',          # Multiple trailing numbers: "Text 1 2 3"
        r'\s*(\(\d+\))+\s*$',      # Multiple parenthesized: "Text (1)(2)"
    ]
    
    # Superscript digits
    SUPERSCRIPT_MAP = {
        '¹': '1', '²': '2', '³': '3', '⁴': '4', '⁵': '5',
        '⁶': '6', '⁷': '7', '⁸': '8', '⁹': '9', '⁰': '0'
    }
    
    @classmethod
    def extract_footnotes(cls, text: str) -> tuple:
        """
        Extract footnote references from text.
        
        Args:
            text: Original text with potential footnote refs
            
        Returns:
            Tuple of (cleaned_text, list_of_footnote_refs)
        """
        if not text or not isinstance(text, str):
            return text, []
        
        footnotes = []
        cleaned = text.strip()
        
        # Handle superscript characters first
        for sup, digit in cls.SUPERSCRIPT_MAP.items():
            if sup in cleaned:
                footnotes.append(digit)
                cleaned = cleaned.replace(sup, '')
        
        # Extract trailing single/multiple numbers like "Text 2" or "Text 2 3"
        trailing_match = re.search(r'\s+(\d(?:\s+\d)*)\s*$', cleaned)
        if trailing_match:
            nums = trailing_match.group(1).split()
            footnotes.extend(nums)
            cleaned = cleaned[:trailing_match.start()].strip()
        
        # Extract parenthesized numbers like "(1)" or "(1)(2)"
        paren_matches = re.findall(r'\((\d+)\)', cleaned)
        if paren_matches:
            footnotes.extend(paren_matches)
            cleaned = re.sub(r'\s*\(\d+\)', '', cleaned).strip()
        
        # Deduplicate while preserving order
        seen = set()
        unique_footnotes = []
        for fn in footnotes:
            if fn not in seen:
                seen.add(fn)
                unique_footnotes.append(fn)
        
        return cleaned, unique_footnotes
    
    @classmethod
    def clean_table_content(cls, table_text: str) -> tuple:
        """
        Clean entire table content, extracting footnotes from row labels.
        
        Args:
            table_text: Full table text in markdown format
            
        Returns:
            Tuple of (cleaned_table_text, dict of {row_label: footnotes})
        """
        if not table_text:
            return table_text, {}
        
        lines = table_text.split('\n')
        cleaned_lines = []
        all_footnotes = {}
        
        for line in lines:
            if '|' not in line or '---' in line:
                # Keep header separators and non-table lines as-is
                cleaned_lines.append(line)
                continue
            
            # Split into cells
            cells = line.split('|')
            cleaned_cells = []
            
            for i, cell in enumerate(cells):
                if i == 1:  # First data column (row label)
                    cleaned_cell, footnotes = cls.extract_footnotes(cell)
                    if footnotes:
                        all_footnotes[cleaned_cell.strip()] = footnotes
                    cleaned_cells.append(cleaned_cell)
                else:
                    cleaned_cells.append(cell)
            
            cleaned_lines.append('|'.join(cleaned_cells))
        
        return '\n'.join(cleaned_lines), all_footnotes


class PDFMetadataExtractor:
    """Extract metadata from PDF filenames and content."""
    
    @staticmethod
    def compute_file_hash(pdf_path: str) -> str:
        """
        Compute MD5 hash of PDF file.
        
        Args:
            pdf_path: Path to PDF file
            
        Returns:
            MD5 hash string
        """
        with open(pdf_path, 'rb') as f:
            return hashlib.md5(f.read()).hexdigest()
    
    @staticmethod
    def extract_year(filename: str) -> Optional[int]:
        """
        Extract year from filename.
        
        Examples:
            10q0925.pdf -> 2025
            10k1222.pdf -> 2022
            
        Args:
            filename: PDF filename
            
        Returns:
            Year or None
        """
        # Pattern: 10q0925 -> month=09, year=25
        match = re.search(r'10[qk](\d{2})(\d{2})', filename.lower())
        if match:
            month, year_suffix = match.groups()
            year = 2000 + int(year_suffix)
            return year
        return None
    
    @staticmethod
    def extract_quarter(filename: str) -> Optional[str]:
        """
        Extract quarter from filename.
        
        Examples:
            10q0925.pdf -> Q3 (September)
            10q0320.pdf -> Q1 (March)
            
        Args:
            filename: PDF filename
            
        Returns:
            Quarter (Q1-Q4) or None
        """
        match = re.search(r'10q(\d{2})\d{2}', filename.lower())
        if match:
            month = int(match.group(1))
            if month in [1, 2, 3]:
                return "Q1"
            elif month in [4, 5, 6]:
                return "Q2"
            elif month in [7, 8, 9]:
                return "Q3"
            elif month in [10, 11, 12]:
                return "Q4"
        return None
    
    @staticmethod
    def extract_report_type(filename: str) -> str:
        """
        Extract report type from filename.
        
        Args:
            filename: PDF filename
            
        Returns:
            Report type (10-Q or 10-K)
        """
        if '10q' in filename.lower():
            return "10-Q"
        elif '10k' in filename.lower():
            return "10-K"
        return "Unknown"
    
    @staticmethod
    def create_metadata(
        pdf_path: str,
        page_no: int,
        table_title: str,
        **kwargs
    ) -> TableMetadata:
        """
        Create TableMetadata from PDF file and table info.
        
        Args:
            pdf_path: Path to PDF file
            page_no: Page number
            table_title: Table title/caption
            **kwargs: Additional metadata fields
            
        Returns:
            TableMetadata object
        """
        filename = Path(pdf_path).name
        
        return TableMetadata(
            source_doc=filename,
            page_no=page_no,
            table_title=table_title,
            year=kwargs.get('year') or PDFMetadataExtractor.extract_year(filename),
            quarter=kwargs.get('quarter') or PDFMetadataExtractor.extract_quarter(filename),
            report_type=kwargs.get('report_type') or PDFMetadataExtractor.extract_report_type(filename),
            extraction_date=kwargs.get('extraction_date') or datetime.now(),
            **{k: v for k, v in kwargs.items() if k not in ['year', 'quarter', 'report_type', 'extraction_date']}
        )


class TableClassifier:
    """Classify financial tables by type."""
    
    TABLE_TYPES = {
        'balance_sheet': [
            'balance sheet', 'statement of financial position',
            'assets', 'liabilities', 'equity'
        ],
        'income_statement': [
            'income statement', 'statement of operations',
            'statement of earnings', 'revenues', 'expenses'
        ],
        'cash_flow': [
            'cash flow', 'statement of cash flows',
            'operating activities', 'investing activities', 'financing activities'
        ],
        'equity': [
            'stockholders equity', 'shareholders equity',
            'statement of equity', 'changes in equity'
        ],
        'notes': [
            'note', 'footnote', 'disclosure'
        ]
    }
    
    @staticmethod
    def classify(title: str) -> str:
        """
        Classify table type from title.
        
        Args:
            title: Table title
            
        Returns:
            Table type category
        """
        title_lower = title.lower()
        
        for table_type, keywords in TableClassifier.TABLE_TYPES.items():
            if any(keyword in title_lower for keyword in keywords):
                return table_type
        
        return 'other'
    
    @staticmethod
    def extract_fiscal_period(table_text: str) -> Optional[str]:
        """
        Extract fiscal period from table headers.
        
        Args:
            table_text: Table text content
            
        Returns:
            Fiscal period string or None
        """
        # Look for patterns like "Three Months Ended March 31, 2025"
        patterns = [
            r'(Three|Six|Nine|Twelve) Months Ended (\w+ \d{1,2}, \d{4})',
            r'Year Ended (\w+ \d{1,2}, \d{4})',
            r'Quarter Ended (\w+ \d{1,2}, \d{4})',
            r'At (\w+ \d{1,2}, \d{4})'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, table_text, re.IGNORECASE)
            if match:
                return match.group(0)
        
        return None
