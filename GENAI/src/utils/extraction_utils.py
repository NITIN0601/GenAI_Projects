"""
Common utilities for PDF extraction and processing.

Consolidates duplicate code from multiple extraction modules.
"""

from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime
import hashlib
import re

import os

from docling.document_converter import DocumentConverter
from docling_core.types.doc import DocItemLabel
from src.domain.tables import TableMetadata


class DoclingHelper:
    """Helper class for common Docling operations."""
    
    @staticmethod
    def convert_pdf(pdf_path: str) -> Any:
        """
        Convert PDF using Docling.
        
        Supports local model loading via environment variables:
        - DOCLING_ARTIFACTS_PATH: Path to local docling models directory
        - DOCLING_OFFLINE: Set to "1" to force offline mode (no downloads)
        
        Args:
            pdf_path: Path to PDF file
            
        Returns:
            Docling conversion result
        """
        # Check for local model path configuration
        artifacts_path = os.environ.get('DOCLING_ARTIFACTS_PATH')
        offline_mode = os.environ.get('DOCLING_OFFLINE', '').lower() in ('1', 'true', 'yes')
        
        # If offline mode requested, set HuggingFace offline environment variables
        if offline_mode:
            os.environ['HF_HUB_OFFLINE'] = '1'
            os.environ['TRANSFORMERS_OFFLINE'] = '1'
        
        if artifacts_path:
            # Use local model path with pipeline options
            from docling.datamodel.pipeline_options import PdfPipelineOptions
            from docling.datamodel.base_models import InputFormat
            from docling.document_converter import PdfFormatOption
            
            pipeline_options = PdfPipelineOptions(
                artifacts_path=artifacts_path
            )
            
            converter = DocumentConverter(
                format_options={
                    InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)
                }
            )
        else:
            # Default: download from HuggingFace Hub
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
            """Clean footnotes, row ranges, section numbers, and extra whitespace from title."""
            if not text:
                return ""
            
            # Remove leading section numbers like "17." or "17 " or "17:"
            text = re.sub(r'^\d+[\.\:\s]+\s*', '', text)
            
            # Remove "Note X" or "Note X." prefix 
            text = re.sub(r'^Note\s+\d+\.?\s*[-–:]?\s*', '', text, flags=re.IGNORECASE)
            
            # Remove "Table X" prefix
            text = re.sub(r'^Table\s+\d+\.?\s*[-–:]?\s*', '', text, flags=re.IGNORECASE)
            
            # Remove row ranges like "(Rows 1-10)" or "(Rows 8-17)"
            text = re.sub(r'\s*\(Rows?\s*\d+[-–]\d+\)\s*$', '', text, flags=re.IGNORECASE)
            
            # Clean footnotes
            # Trailing number: "Text 2"
            text = re.sub(r'\s+\d+\s*$', '', text)
            # Parenthesized: "Text (1)"
            text = re.sub(r'\s*\(\d+\)\s*$', '', text)
            
            # Remove superscript characters
            text = re.sub(r'[¹²³⁴⁵⁶⁷⁸⁹⁰]+', '', text)
            
            return text.strip()[:100]

        def is_valid_title(text: str) -> bool:
            """Check if text is a valid title and not a date/period header or boilerplate."""
            text_lower = text.lower().strip()
            
            # Too short or too long
            if len(text) < 5 or len(text) > 120:
                return False
            
            # Starts with parenthesis (likely not a title)
            if text.startswith('('):
                return False
            
            # Starts with lowercase (likely continuation text)
            if text[0].islower():
                return False
            
            invalid_patterns = [
                # Date/period patterns
                'three months ended', 'six months ended', 'nine months ended', 'twelve months ended',
                'year ended', 'quarter ended', 'at march', 'at december', 'at june', 'at september',
                'as of december', 'as of march', 'as of june', 'as of september',
                # Unit patterns
                '$ in millions', '$ in billions', 'in millions', 'in billions',
                'unaudited', '(unaudited)',
                # Row patterns
                'rows 1-', 'rows 10-', 'rows 8-',
                # Boilerplate/address patterns
                'address of principal', 'executive offices', 'zip code',
                'included within', 'in the balance sheet', 'in the following table',
                'see note', 'see also', 'refer to',
                # Fragment patterns
                'the following', 'as follows', 'shown below', 'presented below',
                # SEC form boilerplate
                'indicate by check mark', 'issuer pursuant', 'registrant',
            ]
            
            for pattern in invalid_patterns:
                if pattern in text_lower:
                    return False
            
            # Must contain at least one letter
            if not any(c.isalpha() for c in text):
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


class CurrencyValueCleaner:
    """
    Clean and merge currency values that are incorrectly split across columns.
    
    Problem Pattern:
        PDF extraction often splits financial values across columns:
        - "$10,207 $" + ",762" (split mid-value)
        - "$ 10" + ",207 $" (leading $ in wrong column)
        
    Solution:
        Detect $ symbols and merge values appropriately:
        - "$10,207 $ 2,762" -> ["$10,207", "$2,762"]
        - "$ 10,207" -> ["$10,207"]
    """
    
    # Pattern to detect currency values
    CURRENCY_PATTERN = re.compile(
        r'^\s*\$?\s*[\d,]+(?:\.\d+)?\s*$'  # Matches: $10,207 or 10,207 or $10.5
    )
    
    # Pattern to detect cell containing only partial currency (ends with $ or starts with comma)
    PARTIAL_CURRENCY_END = re.compile(r'.*\$\s*$')  # Ends with "$" 
    PARTIAL_CURRENCY_START = re.compile(r'^\s*,?\d+')  # Starts with comma/digit (continuation)
    
    @classmethod
    def clean_currency_cells(cls, cells: list) -> list:
        """
        Clean a row of cells, merging incorrectly split currency values.
        
        The key insight: If a cell ends with '$' and the next cell starts with digits,
        they should be merged OR interpreted as separate column values.
        
        Pattern: "$10,207 $ 2,762" in a single cell means:
                 Value1: $10,207 (2024)
                 Value2: $2,762 (2023)
        
        Args:
            cells: List of cell values from a table row
            
        Returns:
            List of cleaned cell values with proper column separation
        """
        if not cells:
            return cells
        
        cleaned = []
        
        for cell in cells:
            if not isinstance(cell, str):
                cleaned.append(cell)
                continue
            
            cell = cell.strip()
            
            # Check if this cell contains multiple currency values
            # Pattern: "$10,207 $ 2,762" or "10,207 2,762" or "$X $Y"
            split_values = cls._split_multi_value_cell(cell)
            
            if len(split_values) > 1:
                # This cell contains multiple values - expand to multiple columns
                cleaned.extend(split_values)
            else:
                # Single value - clean it
                cleaned.append(cls._clean_single_value(cell))
        
        return cleaned
    
    @classmethod
    def _split_multi_value_cell(cls, cell: str) -> list:
        """
        Split a cell containing multiple currency values.
        
        Examples:
            "$10,207 $ 2,762" -> ["$10,207", "$2,762"]
            "10,207 2,762" -> ["10,207", "2,762"]
            "$647 $" -> ["$647"]  (trailing $ is noise)
            "$ 10,207 $ 2,762" -> ["$10,207", "$2,762"]
        """
        if not cell:
            return [cell]
        
        # Pattern: Look for $ followed by number, potentially with another $ and number
        # This handles: "$10,207 $ 2,762" or "$10,207 $2,762"
        multi_currency = re.findall(
            r'\$?\s*([\d,]+(?:\.\d+)?)',  # Capture number groups
            cell
        )
        
        if len(multi_currency) >= 2:
            # Check if there are multiple $ symbols indicating separate values
            dollar_count = cell.count('$')
            
            if dollar_count >= 2 or (dollar_count == 1 and len(multi_currency) >= 2):
                # Multiple values - format each with $ if original had $
                values = []
                for num in multi_currency:
                    num = num.strip()
                    if num and re.match(r'[\d,]+', num):
                        # Only add $ prefix if the original cell had $ symbols
                        if '$' in cell and not num.startswith('$'):
                            values.append(f"${num}")
                        else:
                            values.append(num)
                
                # Filter out empty values
                values = [v for v in values if v and v not in ['$', '']]
                if values:
                    return values
        
        return [cell]
    
    @classmethod
    def _clean_single_value(cls, cell: str) -> str:
        """
        Clean a single cell value.
        
        - Remove trailing $ with no number
        - Normalize spacing around $
        - Remove leading/trailing whitespace
        """
        if not cell:
            return cell
        
        # Remove trailing $ with no numbers after
        cell = re.sub(r'\$\s*$', '', cell)
        
        # Normalize "$ 123" to "$123"
        cell = re.sub(r'\$\s+(\d)', r'$\1', cell)
        
        # Clean multiple spaces
        cell = re.sub(r'\s+', ' ', cell)
        
        return cell.strip()
    
    @classmethod
    def clean_table_rows(cls, table_text: str) -> str:
        """
        Clean all rows in a markdown table, properly splitting multi-value cells.
        
        Args:
            table_text: Markdown table text
            
        Returns:
            Cleaned table text with proper column separation
        """
        if not table_text:
            return table_text
        
        lines = table_text.split('\n')
        cleaned_lines = []
        expected_cols = None
        
        for line in lines:
            if '|' not in line:
                cleaned_lines.append(line)
                continue
            
            if '---' in line or '===' in line:
                # Separator line - track expected columns
                sep_cols = line.count('|') - 1
                if expected_cols is None:
                    expected_cols = sep_cols
                cleaned_lines.append(line)
                continue
            
            # Parse cells
            parts = line.split('|')
            
            # Remove leading/trailing empty parts from |...|
            if parts and not parts[0].strip():
                parts = parts[1:]
            if parts and not parts[-1].strip():
                parts = parts[:-1]
            
            # Clean each cell, potentially expanding multi-value cells
            cleaned_cells = []
            for cell in parts:
                split_values = cls._split_multi_value_cell(cell.strip())
                for val in split_values:
                    cleaned_cells.append(cls._clean_single_value(val))
            
            # Rebuild row
            cleaned_line = '| ' + ' | '.join(cleaned_cells) + ' |'
            cleaned_lines.append(cleaned_line)
        
        return '\n'.join(cleaned_lines)


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
        table_index: int = 0,
        **kwargs
    ) -> TableMetadata:
        """
        Create TableMetadata from PDF file and table info.
        
        Args:
            pdf_path: Path to PDF file
            page_no: Page number
            table_title: Table title/caption
            table_index: Index of table in document (0-based)
            **kwargs: Additional metadata fields
            
        Returns:
            TableMetadata object
        """
        filename = Path(pdf_path).name
        
        # Build table-level metadata
        table_meta = {
            'page_no': page_no,
            'table_title': table_title,
            'table_id': kwargs.pop('table_id', None),
            **kwargs
        }
        
        # Build document-level metadata
        doc_metadata = {
            'year': kwargs.get('year') or PDFMetadataExtractor.extract_year(filename),
            'quarter': kwargs.get('quarter') or PDFMetadataExtractor.extract_quarter(filename),
            'report_type': kwargs.get('report_type') or PDFMetadataExtractor.extract_report_type(filename),
        }
        
        # Use the factory method (single source of truth)
        return TableMetadata.from_extraction(
            table_meta=table_meta,
            doc_metadata=doc_metadata,
            filename=filename,
            table_index=table_index,
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


class TableDataFrameConverter:
    """
    Convert HTML tables to pandas DataFrames for programmatic access.
    
    Provides easy access to table data by column name, with automatic
    handling of currency values and column name normalization.
    
    Usage:
        df = TableDataFrameConverter.html_to_dataframe(html_content)
        print(df['December 31, 2024'])  # Access by column
        print(df.loc['Loans and other receivables'])  # Access by row
    """
    
    @classmethod
    def html_to_dataframe(cls, html_content: str, index_col: int = 0) -> 'pd.DataFrame':
        """
        Convert HTML table to pandas DataFrame.
        
        Args:
            html_content: HTML string containing table(s)
            index_col: Column to use as row index (default: first column)
            
        Returns:
            pandas DataFrame with normalized columns
        """
        try:
            import pandas as pd
            from io import StringIO
        except ImportError:
            raise ImportError("pandas is required for DataFrame conversion: pip install pandas")
        
        # Parse HTML tables
        tables = pd.read_html(StringIO(html_content))
        
        if not tables:
            return pd.DataFrame()
        
        # Use first table
        df = tables[0]
        
        # Clean column names
        df.columns = [cls._normalize_column_name(str(col)) for col in df.columns]
        
        # Set index if valid
        if index_col is not None and 0 <= index_col < len(df.columns):
            index_name = df.columns[index_col]
            df = df.set_index(index_name)
            df.index = [cls._normalize_row_label(str(idx)) for idx in df.index]
        
        # Clean currency values in all cells
        for col in df.columns:
            df[col] = df[col].apply(cls._clean_currency_value)
        
        return df
    
    @classmethod
    def markdown_to_dataframe(cls, markdown_content: str, index_col: int = 0) -> 'pd.DataFrame':
        """
        Convert markdown table to pandas DataFrame.
        
        Args:
            markdown_content: Markdown table string
            index_col: Column to use as row index
            
        Returns:
            pandas DataFrame
        """
        try:
            import pandas as pd
        except ImportError:
            raise ImportError("pandas is required for DataFrame conversion: pip install pandas")
        
        lines = [line.strip() for line in markdown_content.split('\n') if line.strip()]
        
        # Find header and data
        header_line = None
        data_lines = []
        
        for i, line in enumerate(lines):
            if '|' not in line:
                continue
            if '---' in line or '===' in line:
                continue  # Skip separator
            
            if header_line is None:
                header_line = line
            else:
                data_lines.append(line)
        
        if not header_line:
            return pd.DataFrame()
        
        # Parse header
        header_parts = [p.strip() for p in header_line.split('|') if p.strip()]
        
        # Parse data rows
        rows = []
        for line in data_lines:
            parts = [p.strip() for p in line.split('|') if p.strip()]
            # Pad or truncate to match header length
            while len(parts) < len(header_parts):
                parts.append('')
            parts = parts[:len(header_parts)]
            rows.append(parts)
        
        # Create DataFrame
        df = pd.DataFrame(rows, columns=header_parts)
        
        # Set index
        if index_col is not None and 0 <= index_col < len(df.columns):
            index_name = df.columns[index_col]
            df = df.set_index(index_name)
        
        return df
    
    @classmethod
    def extract_column_values(cls, df: 'pd.DataFrame', column_pattern: str) -> dict:
        """
        Extract values from columns matching a pattern.
        
        Args:
            df: pandas DataFrame
            column_pattern: Regex pattern to match column names (e.g., "2024|2023")
            
        Returns:
            Dict of {column_name: {row_label: value}}
        """
        import re
        
        result = {}
        for col in df.columns:
            if re.search(column_pattern, str(col), re.IGNORECASE):
                result[col] = df[col].to_dict()
        
        return result
    
    @classmethod
    def compare_periods(cls, df: 'pd.DataFrame', period1: str, period2: str) -> 'pd.DataFrame':
        """
        Create comparison DataFrame between two periods.
        
        Args:
            df: Source DataFrame with period columns
            period1: Column name/pattern for first period (e.g., "2024")
            period2: Column name/pattern for second period (e.g., "2023")
            
        Returns:
            DataFrame with columns: [Row Label, Period1, Period2, Change, Change %]
        """
        import pandas as pd
        
        # Find matching columns
        col1 = cls._find_column(df, period1)
        col2 = cls._find_column(df, period2)
        
        if col1 is None or col2 is None:
            raise ValueError(f"Could not find columns for periods: {period1}, {period2}")
        
        # Build comparison
        comparison = pd.DataFrame({
            'Category': df.index,
            period1: df[col1].values,
            period2: df[col2].values,
        })
        
        # Calculate change (handle non-numeric)
        def calc_change(row):
            try:
                v1 = cls._parse_currency(row[period1])
                v2 = cls._parse_currency(row[period2])
                return v1 - v2
            except (ValueError, TypeError):
                return None
        
        def calc_pct(row):
            try:
                v1 = cls._parse_currency(row[period1])
                v2 = cls._parse_currency(row[period2])
                if v2 != 0:
                    return ((v1 - v2) / abs(v2)) * 100
                return None
            except (ValueError, TypeError, ZeroDivisionError):
                return None
        
        comparison['Change'] = comparison.apply(calc_change, axis=1)
        comparison['Change %'] = comparison.apply(calc_pct, axis=1)
        
        return comparison.set_index('Category')
    
    @staticmethod
    def _find_column(df: 'pd.DataFrame', pattern: str) -> str:
        """Find column matching pattern."""
        import re
        for col in df.columns:
            if re.search(pattern, str(col), re.IGNORECASE):
                return col
        return None
    
    @staticmethod
    def _normalize_column_name(name: str) -> str:
        """Normalize column name."""
        # Remove excessive whitespace
        name = re.sub(r'\s+', ' ', name).strip()
        return name
    
    @staticmethod
    def _normalize_row_label(label: str) -> str:
        """Normalize row label."""
        # Remove footnote numbers
        label = re.sub(r'\s+\d+$', '', label)
        label = re.sub(r'\(\d+\)$', '', label)
        return label.strip()
    
    @staticmethod
    def _clean_currency_value(value) -> str:
        """Clean currency value for display."""
        if pd.isna(value):
            return ''
        value = str(value).strip()
        # Normalize spacing around $
        value = re.sub(r'\$\s+', '$', value)
        # Remove extra whitespace
        value = re.sub(r'\s+', ' ', value)
        return value
    
    @staticmethod
    def _parse_currency(value) -> float:
        """Parse currency string to float."""
        if not value or pd.isna(value):
            return 0.0
        # Remove currency symbols and commas
        cleaned = re.sub(r'[$,\s]', '', str(value))
        # Handle parentheses for negative
        if cleaned.startswith('(') and cleaned.endswith(')'):
            cleaned = '-' + cleaned[1:-1]
        return float(cleaned)


# Need pd in scope for type hints  
try:
    import pandas as pd
except ImportError:
    pd = None

