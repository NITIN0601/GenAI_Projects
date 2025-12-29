"""
Common utilities for PDF extraction and processing.

This module provides utility classes for:
- FootnoteExtractor: Extract and clean footnote references from table content
- CurrencyValueCleaner: Clean and merge incorrectly split currency values
- PDFMetadataExtractor: Extract metadata from PDF filenames and content
- TableClassifier: Classify financial tables by type
- TableDataFrameConverter: Convert HTML/markdown tables to pandas DataFrames

NOTE: DoclingHelper has been COMPLETELY MOVED to:
      src.infrastructure.extraction.helpers.DoclingHelper
      Import from the new location directly - no re-export here to avoid circular imports.
"""

from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime
import hashlib
import re
import os

from src.domain.tables import TableMetadata
from src.utils.logger import get_logger

logger = get_logger(__name__)

__all__ = ['FootnoteExtractor', 'CurrencyValueCleaner', 
           'PDFMetadataExtractor', 'TableClassifier', 'TableDataFrameConverter']


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
        
        # Handle attached comma-separated footnotes like "ROTCE2,3" or "ROTCE2, 3"
        attached_comma_match = re.search(r'([a-zA-Z])(\d+(?:,\s*\d+)*),?\s*$', cleaned)
        if attached_comma_match:
            fn_part = attached_comma_match.group(2)
            fn_nums = re.findall(r'\d+', fn_part)
            if fn_nums:
                footnotes.extend(fn_nums)
                cleaned = cleaned[:attached_comma_match.start()] + attached_comma_match.group(1)
        
        # Handle trailing comma-separated footnotes with space
        trailing_comma_match = re.search(r'\s+(\d+(?:,\s*\d+)+),?\s*$', cleaned)
        if trailing_comma_match:
            fn_part = trailing_comma_match.group(1)
            fn_nums = re.findall(r'\d+', fn_part)
            if fn_nums:
                footnotes.extend(fn_nums)
                cleaned = cleaned[:trailing_comma_match.start()].strip()
        
        # Extract trailing single/multiple numbers
        trailing_match = re.search(r'\s+(\d(?:\s+\d)*)\s*$', cleaned)
        if trailing_match:
            nums = trailing_match.group(1).split()
            footnotes.extend(nums)
            cleaned = cleaned[:trailing_match.start()].strip()
        
        # Extract parenthesized numbers
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
                cleaned_lines.append(line)
                continue
            
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
    
    CURRENCY_PATTERN = re.compile(r'^\s*\$?\s*[\d,]+(?:\.\d+)?\s*$')
    PARTIAL_CURRENCY_END = re.compile(r'.*\$\s*$')
    PARTIAL_CURRENCY_START = re.compile(r'^\s*,?\d+')
    
    @classmethod
    def clean_currency_cells(cls, cells: list) -> list:
        """Clean a row of cells, merging incorrectly split currency values."""
        if not cells:
            return cells
        
        cleaned = []
        
        for cell in cells:
            if not isinstance(cell, str):
                cleaned.append(cell)
                continue
            
            cell = cell.strip()
            split_values = cls._split_multi_value_cell(cell)
            
            if len(split_values) > 1:
                cleaned.extend(split_values)
            else:
                cleaned.append(cls._clean_single_value(cell))
        
        return cleaned
    
    @classmethod
    def _split_multi_value_cell(cls, cell: str) -> list:
        """Split a cell containing multiple currency values."""
        if not cell:
            return [cell]
        
        # Preserve date headers
        cell_lower = cell.lower()
        date_months = ['january', 'february', 'march', 'april', 'may', 'june', 
                       'july', 'august', 'september', 'october', 'november', 'december']
        is_date_header = (
            any(month in cell_lower for month in date_months) and
            re.search(r'\b20[0-3]\d\b', cell)
        )
        if is_date_header:
            return [cell]
        
        if cell_lower.startswith('at ') or cell_lower.startswith('as of '):
            return [cell]
        
        # Check for label followed by multiple currency values
        label_then_values = re.match(
            r'^([A-Za-z][A-Za-z\s]*?)\s+(\$?\s*[\d,\(\)\-]+(?:\s+\$?\s*[\d,\(\)\-]+)+)\s*$',
            cell
        )
        
        if label_then_values:
            label = label_then_values.group(1).strip()
            values_part = label_then_values.group(2)
            
            values = re.findall(
                r'\$?\s*[\d,]+(?:\.\d+)?|\$?\s*\([\d,]+(?:\.\d+)?\)',
                values_part
            )
            
            if len(values) >= 2:
                cleaned_values = []
                for val in values:
                    val = val.strip()
                    if val:
                        val = re.sub(r'\$\s+', '$', val)
                        val = re.sub(r'\s+', ' ', val)
                        if val and val not in ['$', '']:
                            cleaned_values.append(val)
                
                if cleaned_values:
                    return [label] + cleaned_values
        
        if re.search(r'[a-zA-Z]', cell):
            return [cell]
        
        multi_currency = re.findall(r'\$?\s*([\d,]+(?:\.\d+)?)', cell)
        
        if len(multi_currency) >= 2:
            dollar_count = cell.count('$')
            
            if dollar_count >= 2 or (dollar_count == 1 and len(multi_currency) >= 2):
                values = []
                for num in multi_currency:
                    num = num.strip()
                    if num and re.match(r'[\d,]+', num):
                        if '$' in cell and not num.startswith('$'):
                            values.append(f"${num}")
                        else:
                            values.append(num)
                
                values = [v for v in values if v and v not in ['$', '']]
                if values:
                    return values
        
        return [cell]
    
    @classmethod
    def _clean_single_value(cls, cell: str) -> str:
        """Clean a single cell value."""
        if not cell:
            return cell
        
        cell = re.sub(r'\$\s*$', '', cell)
        cell = re.sub(r'\$\s+(\d)', r'$\1', cell)
        cell = re.sub(r'\s+', ' ', cell)
        
        return cell.strip()
    
    @classmethod
    def clean_table_rows(cls, table_text: str) -> str:
        """Clean all rows in a markdown table, properly splitting multi-value cells."""
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
                sep_cols = line.count('|') - 1
                if expected_cols is None:
                    expected_cols = sep_cols
                cleaned_lines.append(line)
                continue
            
            parts = line.split('|')
            
            if parts and not parts[0].strip():
                parts = parts[1:]
            if parts and not parts[-1].strip():
                parts = parts[:-1]
            
            cleaned_cells = []
            for cell in parts:
                split_values = cls._split_multi_value_cell(cell.strip())
                for val in split_values:
                    cleaned_val = cls._clean_single_value(val)
                    
                    if re.match(r'^[\d\s,]+,$', cleaned_val):
                        continue
                    
                    cleaned_cells.append(cleaned_val)
            
            cleaned_line = '| ' + ' | '.join(cleaned_cells) + ' |'
            cleaned_lines.append(cleaned_line)
        
        return '\n'.join(cleaned_lines)


class PDFMetadataExtractor:
    """Extract metadata from PDF filenames and content."""
    
    @staticmethod
    def compute_file_hash(pdf_path: str) -> str:
        """Compute MD5 hash of PDF file."""
        from src.utils.helpers import compute_file_hash
        return compute_file_hash(pdf_path)
    
    @staticmethod
    def extract_year(filename: str) -> Optional[int]:
        """Extract year from filename (e.g., 10q0925.pdf -> 2025)."""
        match = re.search(r'10[qk](\d{2})(\d{2})', filename.lower())
        if match:
            month, year_suffix = match.groups()
            year = 2000 + int(year_suffix)
            return year
        return None
    
    @staticmethod
    def extract_quarter(filename: str) -> Optional[str]:
        """Extract quarter from filename (e.g., 10q0925.pdf -> Q3)."""
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
        """Extract report type from filename (10-Q or 10-K)."""
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
        """Create TableMetadata from PDF file and table info."""
        filename = Path(pdf_path).name
        
        table_meta = {
            'page_no': page_no,
            'table_title': table_title,
            'table_id': kwargs.pop('table_id', None),
            **kwargs
        }
        
        doc_metadata = {
            'year': kwargs.get('year') or PDFMetadataExtractor.extract_year(filename),
            'quarter': kwargs.get('quarter') or PDFMetadataExtractor.extract_quarter(filename),
            'report_type': kwargs.get('report_type') or PDFMetadataExtractor.extract_report_type(filename),
        }
        
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
        """Classify table type from title."""
        title_lower = title.lower()
        
        for table_type, keywords in TableClassifier.TABLE_TYPES.items():
            if any(keyword in title_lower for keyword in keywords):
                return table_type
        
        return 'other'
    
    @staticmethod
    def extract_fiscal_period(table_text: str) -> Optional[str]:
        """Extract fiscal period from table headers."""
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
    Convert HTML/markdown tables to pandas DataFrames for programmatic access.
    
    Usage:
        df = TableDataFrameConverter.html_to_dataframe(html_content)
        print(df['December 31, 2024'])  # Access by column
        print(df.loc['Loans and other receivables'])  # Access by row
    """
    
    @classmethod
    def html_to_dataframe(cls, html_content: str, index_col: int = 0) -> 'pd.DataFrame':
        """Convert HTML table to pandas DataFrame."""
        try:
            import pandas as pd
            from io import StringIO
        except ImportError:
            raise ImportError("pandas is required: pip install pandas")
        
        tables = pd.read_html(StringIO(html_content))
        
        if not tables:
            return pd.DataFrame()
        
        df = tables[0]
        df.columns = [cls._normalize_column_name(str(col)) for col in df.columns]
        
        if index_col is not None and 0 <= index_col < len(df.columns):
            index_name = df.columns[index_col]
            df = df.set_index(index_name)
            df.index = [cls._normalize_row_label(str(idx)) for idx in df.index]
        
        for col in df.columns:
            df[col] = df[col].apply(cls._clean_currency_value)
        
        return df
    
    @classmethod
    def markdown_to_dataframe(cls, markdown_content: str, index_col: int = 0) -> 'pd.DataFrame':
        """Convert markdown table to pandas DataFrame."""
        try:
            import pandas as pd
        except ImportError:
            raise ImportError("pandas is required: pip install pandas")
        
        lines = [line.strip() for line in markdown_content.split('\n') if line.strip()]
        
        header_line = None
        data_lines = []
        
        for line in lines:
            if '|' not in line:
                continue
            if '---' in line or '===' in line:
                continue
            
            if header_line is None:
                header_line = line
            else:
                data_lines.append(line)
        
        if not header_line:
            return pd.DataFrame()
        
        header_parts = [p.strip() for p in header_line.split('|') if p.strip()]
        
        rows = []
        for line in data_lines:
            parts = [p.strip() for p in line.split('|') if p.strip()]
            while len(parts) < len(header_parts):
                parts.append('')
            parts = parts[:len(header_parts)]
            rows.append(parts)
        
        df = pd.DataFrame(rows, columns=header_parts)
        
        if index_col is not None and 0 <= index_col < len(df.columns):
            index_name = df.columns[index_col]
            df = df.set_index(index_name)
        
        return df
    
    @classmethod
    def extract_column_values(cls, df: 'pd.DataFrame', column_pattern: str) -> dict:
        """Extract values from columns matching a pattern."""
        result = {}
        for col in df.columns:
            if re.search(column_pattern, str(col), re.IGNORECASE):
                result[col] = df[col].to_dict()
        return result
    
    @classmethod
    def compare_periods(cls, df: 'pd.DataFrame', period1: str, period2: str) -> 'pd.DataFrame':
        """Create comparison DataFrame between two periods."""
        import pandas as pd
        
        col1 = cls._find_column(df, period1)
        col2 = cls._find_column(df, period2)
        
        if col1 is None or col2 is None:
            raise ValueError(f"Could not find columns for periods: {period1}, {period2}")
        
        comparison = pd.DataFrame({
            'Category': df.index,
            period1: df[col1].values,
            period2: df[col2].values,
        })
        
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
        for col in df.columns:
            if re.search(pattern, str(col), re.IGNORECASE):
                return col
        return None
    
    @staticmethod
    def _normalize_column_name(name: str) -> str:
        """Normalize column name."""
        name = re.sub(r'\s+', ' ', name).strip()
        return name
    
    @staticmethod
    def _normalize_row_label(label: str) -> str:
        """Normalize row label."""
        label = re.sub(r'\s+\d+$', '', label)
        label = re.sub(r'\(\d+\)$', '', label)
        return label.strip()
    
    @staticmethod
    def _clean_currency_value(value) -> str:
        """Clean currency value for display."""
        try:
            import pandas as pd
            if pd.isna(value):
                return ''
        except:
            if value is None:
                return ''
        value = str(value).strip()
        value = re.sub(r'\$\s+', '$', value)
        value = re.sub(r'\s+', ' ', value)
        return value
    
    @staticmethod
    def _parse_currency(value) -> float:
        """Parse currency string to float."""
        if not value:
            return 0.0
        try:
            import pandas as pd
            if pd.isna(value):
                return 0.0
        except:
            pass
        cleaned = re.sub(r'[$,\s]', '', str(value))
        if cleaned.startswith('(') and cleaned.endswith(')'):
            cleaned = '-' + cleaned[1:-1]
        return float(cleaned)
