"""Metadata extraction from financial PDFs."""

import re
from typing import Optional, Dict, Any
from datetime import datetime
from pathlib import Path

from src.models.schemas import TableMetadata


class MetadataExtractor:
    """Extract rich metadata from financial documents."""
    
    # Patterns for extracting information
    YEAR_PATTERN = re.compile(r'20\d{2}')
    QUARTER_PATTERN = re.compile(r'(Q[1-4]|First|Second|Third|Fourth)\s+(Quarter|quarter)', re.IGNORECASE)
    
    # Table type keywords
    TABLE_TYPES = {
        'balance sheet': 'Balance Sheet',
        'statement of financial condition': 'Balance Sheet',
        'assets and liabilities': 'Balance Sheet',
        'income statement': 'Income Statement',
        'statement of earnings': 'Income Statement',
        'statement of operations': 'Income Statement',
        'cash flow': 'Cash Flow Statement',
        'statement of cash flows': 'Cash Flow Statement',
        'shareholders equity': 'Shareholders Equity',
        'stockholders equity': 'Shareholders Equity',
        'comprehensive income': 'Comprehensive Income',
        'fair value': 'Fair Value',
        'derivative': 'Derivatives',
        'segment': 'Segment Information',
    }
    
    def __init__(self, filename: str):
        self.filename = Path(filename).name
        
    def extract_metadata(
        self,
        table_title: str,
        page_no: int,
        table_content: Optional[str] = None
    ) -> TableMetadata:
        """Extract comprehensive metadata from table information."""
        
        # Extract year
        year = self._extract_year()
        
        # Extract quarter
        quarter = self._extract_quarter()
        
        # Determine report type
        report_type = self._extract_report_type()
        
        # Extract table type
        table_type = self._extract_table_type(table_title)
        
        # Extract fiscal period from title
        fiscal_period = self._extract_fiscal_period(table_title, table_content)
        
        return TableMetadata(
            source_doc=self.filename,
            page_no=page_no,
            table_title=table_title,
            year=year,
            quarter=quarter,
            report_type=report_type,
            table_type=table_type,
            fiscal_period=fiscal_period
        )
    
    def _extract_year(self) -> int:
        """Extract year from filename."""
        # Filename format: 10q0625.pdf or 10k1224.pdf
        # Last 2 digits are year (e.g., 25 = 2025, 24 = 2024)
        match = re.search(r'(\d{2})\.pdf$', self.filename)
        if match:
            year_suffix = int(match.group(1))
            # Assume 20xx for years
            return 2000 + year_suffix
        
        # Fallback: search for 4-digit year in filename
        years = self.YEAR_PATTERN.findall(self.filename)
        if years:
            return int(years[-1])
        
        # Default to current year
        return datetime.now().year
    
    def _extract_quarter(self) -> Optional[str]:
        """Extract quarter from filename."""
        # Filename format: 10q0625.pdf
        # First 2 digits after 'q' are month (06 = Q2, 03 = Q1, 09 = Q3, 12 = Q4)
        match = re.search(r'10q(\d{2})', self.filename.lower())
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
    
    def _extract_report_type(self) -> str:
        """Extract report type from filename."""
        filename_lower = self.filename.lower()
        if '10k' in filename_lower:
            return "10-K"
        elif '10q' in filename_lower:
            return "10-Q"
        return "Unknown"
    
    def _extract_table_type(self, title: str) -> Optional[str]:
        """Extract table type from title."""
        title_lower = title.lower()
        
        for keyword, table_type in self.TABLE_TYPES.items():
            if keyword in title_lower:
                return table_type
        
        return None
    
    def _extract_fiscal_period(
        self,
        title: str,
        content: Optional[str] = None
    ) -> Optional[str]:
        """Extract fiscal period from title or content."""
        # Look for date patterns like "June 30, 2025" or "As of December 31, 2024"
        date_patterns = [
            r'(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+20\d{2}',
            r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\.?\s+\d{1,2},?\s+20\d{2}',
            r'20\d{2}-\d{2}-\d{2}',
        ]
        
        text = title
        if content:
            text = f"{title} {content[:200]}"  # Check first 200 chars of content
        
        for pattern in date_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(0)
        
        return None
    
    def extract_additional_metadata(self, table_title: str, headers: list) -> Dict[str, Any]:
        """Extract additional metadata from table structure."""
        metadata = {}
        
        # Check if table has time series data
        headers_str = ' '.join(str(h).lower() for h in headers)
        
        # Detect time periods in headers
        if any(year in headers_str for year in ['2024', '2025', '2023']):
            metadata['has_time_series'] = True
        
        # Detect currency
        if any(curr in headers_str for curr in ['$', 'usd', 'dollars']):
            metadata['currency'] = 'USD'
        
        # Detect units
        if 'millions' in headers_str:
            metadata['units'] = 'millions'
        elif 'billions' in headers_str:
            metadata['units'] = 'billions'
        elif 'thousands' in headers_str:
            metadata['units'] = 'thousands'
        
        return metadata
