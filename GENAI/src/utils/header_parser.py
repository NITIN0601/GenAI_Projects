"""
Multi-Level Header Parser - Dynamic header detection from multi-row tables.

Standalone module for parsing complex table headers with multiple levels.
Used by: table_merger.py, consolidated_exporter.py
"""

import re
from typing import Dict, List

from src.utils.quarter_mapper import QuarterDateMapper


class MultiLevelHeaderParser:
    """
    Parse multi-row table headers to detect L1/L2/L3/L4 levels dynamically.
    
    Handles scenarios like:
    - Spanning headers (date spanning multiple category columns)
    - Category headers (Standardized, Advanced, Assets, Liabilities)
    - Period types (Three Months Ended, Six Months Ended)
    - Dates (At June 30, 2024, or just 2024)
    - Static columns (no date context, like Total, Corporate)
    """
    
    # Patterns that indicate L2 (Period Type)
    PERIOD_TYPE_PATTERNS = [
        'three months ended', 'six months ended', 'nine months ended',
        'year ended', 'fiscal year ended', 'quarter ended',
    ]
    
    # Patterns that indicate L3 (Date) - point-in-time
    DATE_PATTERNS = [
        r'at\s+\w+\s+\d+,?\s*\d{4}',      # At June 30, 2024
        r'as of\s+\w+\s+\d+,?\s*\d{4}',   # As of June 30, 2024
        r'\d{1,2}Q\s*\d{4}',               # 4Q 2024
        r'Q\d\s*\d{4}',                    # Q1 2024
        r'^20\d{2}$',                       # 2024 (year only)
    ]
    
    # Patterns that indicate L1 (Category/Main Header)
    CATEGORY_PATTERNS = [
        'assets', 'liabilities', 'liability', 'average', 'ending balance',
        'beginning balance', 'amortized cost', 'fair value', 'carrying value',
        'net revenue', 'standardized', 'advanced', 'level 1', 'level 2', 'level 3',
        'bilateral', 'cleared', 'exchange-traded', 'contractual', 'regulatory',
    ]
    
    # Static column indicators (no date, no merge)
    STATIC_PATTERNS = [
        'total', 'corporate', 'other', 'minimum', 'maximum', 'high', 'low',
        'average', 'period end', 'loans', 'commitments', 'cre', 'residential',
    ]
    
    @classmethod
    def parse_multi_row_headers(
        cls,
        header_rows: list,
        source_filename: str = ''
    ) -> dict:
        """
        Parse multiple header rows to extract L1/L2/L3/L4 for each column.
        
        Args:
            header_rows: List of lists, each inner list is a row of column values
                         Example: [['', 'At June 30, 2024'], ['$ in millions', 'Col1', 'Col2']]
            source_filename: Source filename for 10-K detection
            
        Returns:
            Dict with:
                'columns': List of column dicts with L1, L2, L3, L4, code, is_static
                'spanning_l1': Detected spanning L1 header
                'spanning_l3': Detected spanning L3 (date) header
        """
        result = {
            'columns': [],
            'spanning_l1': '',
            'spanning_l2': '',
            'spanning_l3': '',
        }
        
        if not header_rows:
            return result
        
        # Flatten and analyze each row
        num_cols = max(len(row) for row in header_rows) if header_rows else 0
        
        # Initialize column info
        for col_idx in range(num_cols):
            result['columns'].append({
                'l1': '',
                'l2': '',
                'l3': '',
                'l4': '',
                'code': '',
                'is_static': False,
            })
        
        # First pass: detect spanning headers (usually in first rows)
        spanning_date = ''
        spanning_period = ''
        spanning_category = ''
        
        for row_idx, row in enumerate(header_rows):
            for col_idx, cell in enumerate(row):
                cell_str = str(cell).strip() if cell else ''
                if not cell_str or cell_str.lower() in ['', 'nan', 'none', '$ in millions', '$ in billions']:
                    continue
                
                cell_lower = cell_str.lower()
                
                # Check for date in cell (spanning date like "At June 30, 2024 and December 31, 2023")
                if 'and' in cell_lower and ('at ' in cell_lower or 'as of' in cell_lower):
                    # Multi-date spanning header
                    spanning_date = cell_str
                    result['spanning_l3'] = cell_str
                
                # Check for period type spanning
                for pattern in cls.PERIOD_TYPE_PATTERNS:
                    if pattern in cell_lower:
                        spanning_period = cell_str
                        result['spanning_l2'] = cell_str
                        break
                
                # Check for date patterns (single date)
                if not spanning_date:
                    for date_pat in cls.DATE_PATTERNS:
                        if re.search(date_pat, cell_lower, re.IGNORECASE):
                            # This is a date header - could be spanning
                            if cls._count_non_empty_cells(row) == 1:
                                spanning_date = cell_str
                                result['spanning_l3'] = cell_str
                            break
                
                # Check for category patterns (L1)
                for cat_pattern in cls.CATEGORY_PATTERNS:
                    if cat_pattern in cell_lower:
                        if cls._count_non_empty_cells(row) <= 2:
                            spanning_category = cell_str
                            result['spanning_l1'] = cell_str
                        break
        
        # Second pass: assign L1/L2/L3/L4 to each column
        for col_idx in range(num_cols):
            col_values = [row[col_idx] if col_idx < len(row) else '' for row in header_rows]
            col_values = [str(v).strip() if v else '' for v in col_values]
            
            col_info = cls._parse_column_headers(
                col_values, 
                spanning_date, 
                spanning_period, 
                spanning_category,
                source_filename
            )
            
            result['columns'][col_idx].update(col_info)
        
        return result
    
    @classmethod
    def _count_non_empty_cells(cls, row: list) -> int:
        """Count non-empty cells in a row (excluding $ in millions type)."""
        count = 0
        for cell in row:
            cell_str = str(cell).strip() if cell else ''
            if cell_str and cell_str.lower() not in ['', 'nan', 'none', '$ in millions', '$ in billions']:
                count += 1
        return count
    
    @classmethod
    def _parse_column_headers(
        cls,
        col_values: list,
        spanning_date: str,
        spanning_period: str,
        spanning_category: str,
        source_filename: str
    ) -> dict:
        """
        Parse column values to determine L1/L2/L3/L4.
        
        Args:
            col_values: List of values from top to bottom for this column
            spanning_date: Spanning date header if detected
            spanning_period: Spanning period type if detected
            spanning_category: Spanning category if detected
            source_filename: Source filename for 10-K detection
        """
        result = {
            'l1': spanning_category,
            'l2': spanning_period,
            'l3': '',
            'l4': '',
            'code': '',
            'is_static': False,
        }
        
        # Combine all column values and analyze
        combined = ' '.join([v for v in col_values if v and v.lower() not in ['nan', 'none', '$ in millions', '$ in billions']])
        combined_lower = combined.lower()
        
        if not combined:
            return result
        
        # Check for L4 (sub-category like Period End, Average, High, Low)
        l4_patterns = ['period end', 'average', 'high', 'low', 'total']
        is_l4_subcategory = False
        for l4_pat in l4_patterns:
            if l4_pat == combined_lower.strip() or combined_lower.strip().startswith(l4_pat):
                result['l4'] = combined
                is_l4_subcategory = True
                break
        
        # Check if this is a static column (no date)
        # Static only if: no date in column, no spanning date, no spanning period
        for static_pat in cls.STATIC_PATTERNS:
            if combined_lower == static_pat or combined_lower.startswith(static_pat + ' '):
                has_date = any(re.search(p, combined_lower, re.IGNORECASE) for p in cls.DATE_PATTERNS)
                if not has_date and not spanning_date and not spanning_period:
                    result['is_static'] = True
                    result['l4'] = combined
                    result['code'] = 'STATIC'
                    return result
        
        # Try to extract date from column values, spanning date, OR spanning period
        date_source = ''
        if spanning_date:
            date_source = spanning_date
        elif spanning_period:
            date_source = spanning_period  # Period may contain date like "Three Months Ended June 30,2024"
        else:
            date_source = combined
        
        # Check for period type in column
        period_found = spanning_period
        for pattern in cls.PERIOD_TYPE_PATTERNS:
            if pattern in combined_lower:
                period_found = pattern.title()
                result['l2'] = period_found
                break
            elif pattern in spanning_period.lower():
                result['l2'] = pattern.title()
                break
        
        # Check for date (in column, spanning date, or spanning period)
        all_sources = f"{combined} {spanning_date} {spanning_period}"
        year_match = re.search(r'(20\d{2})', all_sources)
        if year_match:
            year = year_match.group(1)
            
            # Determine quarter from month in any source
            quarter = 'Q4'  # Default
            for month, qtr in QuarterDateMapper.MONTH_TO_QUARTER.items():
                if month in all_sources.lower():
                    quarter = qtr
                    break
            
            # Build code based on period type
            period_check = f"{combined_lower} {spanning_period.lower()}"
            if 'three months' in period_check:
                result['code'] = f"{quarter}-QTD-{year}"
                result['l2'] = 'Three Months Ended'
            elif 'six months' in period_check:
                result['code'] = f"{quarter}-YTD-{year}"
                result['l2'] = 'Six Months Ended'
            elif 'nine months' in period_check:
                result['code'] = f"{quarter}-YTD-{year}"
                result['l2'] = 'Nine Months Ended'
            elif 'year ended' in period_check or '10k' in source_filename.lower():
                result['code'] = f"YTD-{year}"
                result['l2'] = 'Year Ended'
            else:
                # Point-in-time
                result['code'] = f"{quarter}-{year}"
            
            # Set L3 as display date
            result['l3'] = QuarterDateMapper.code_to_display(result['code'])
        
        # Check for category in column (override spanning if column-specific)
        for cat_pattern in cls.CATEGORY_PATTERNS:
            if cat_pattern in combined_lower:
                # Check if this is actually a category (not part of a date or sub-category)
                if cat_pattern not in ['average'] and not is_l4_subcategory:
                    result['l1'] = combined
                break
        
        return result
