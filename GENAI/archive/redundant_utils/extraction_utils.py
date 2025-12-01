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
from models.schemas import TableMetadata


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
