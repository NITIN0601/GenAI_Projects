"""
Multi-Row Column Header Normalizer - Enhanced pattern handling for financial tables.

Handles complex multi-row spanning headers and normalizes to standardized codes.
Integrates with existing: QuarterDateMapper, MetadataLabels, MetadataBuilder

Output Formats:
    - Point-in-time:     Qn-YYYY           (At March 31, 2024 → Q1-2024)
    - Quarter-to-date:   Qn-QTD-YYYY       (Three Months Ended → Q1-QTD-2024)
    - Year-to-date:      Qn-YTD-YYYY       (Six/Nine Months Ended → Q2-YTD-2024)
    - Fiscal quarter:    nQ-YYYY           (4Q 2024 → 4Q-2024)
    - With category:     Qn-YYYY Category  (Q2-2024 Trading)
    - Combined dates:    Qn-YYYY & Qn-YYYY
"""

import re
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass, field


@dataclass
class ColumnContext:
    """Context accumulated for a single column across header rows."""
    l1_header: str = ''      # Main header (e.g., "Average Monthly Balance")
    period_type: str = ''    # Period type (e.g., "Three Months Ended")
    month: str = ''          # Month name (e.g., "March", "June")
    year: str = ''           # Year (e.g., "2024")
    category: str = ''       # Category suffix (e.g., "Trading", "IS")
    is_date_column: bool = True  # False for non-date columns like "% Change"
    raw_values: List[str] = field(default_factory=list)


class MultiRowHeaderNormalizer:
    """
    Normalize multi-row spanning headers into standardized Qn-YYYY codes.
    
    Handles all 8 pattern groups:
        1. Simple point-in-time (At March 31, 2024)
        2. Period-based (Three/Six/Nine Months Ended)
        3. Period + non-date columns (% Change)
        4. Period + category combinations
        5. Nested headers (L1 + period + year)
        6. Fiscal quarter notation (4Q 2024)
        7. Combined dates (At June 30, 2024 and December 31, 2023)
        8. Specialized patterns
    """
    
    # Month to quarter mapping
    MONTH_TO_QUARTER = {
        'january': 'Q1', 'february': 'Q1', 'march': 'Q1',
        'april': 'Q2', 'may': 'Q2', 'june': 'Q2',
        'july': 'Q3', 'august': 'Q3', 'september': 'Q3',
        'october': 'Q4', 'november': 'Q4', 'december': 'Q4',
        # Abbreviated months
        'jan': 'Q1', 'feb': 'Q1', 'mar': 'Q1',
        'apr': 'Q2', 'jun': 'Q2',
        'jul': 'Q3', 'aug': 'Q3', 'sep': 'Q3', 'sept': 'Q3',
        'oct': 'Q4', 'nov': 'Q4', 'dec': 'Q4',
    }
    
    # Period type patterns and their output codes
    PERIOD_PATTERNS = [
        (r'three\s+months?\s+ended', 'QTD'),
        (r'six\s+months?\s+ended', 'YTD'),
        (r'nine\s+months?\s+ended', 'YTD'),
        (r'year\s+ended', 'ANNUAL'),
        (r'fiscal\s+year\s+ended', 'ANNUAL'),
    ]
    
    # Point-in-time patterns
    POINT_IN_TIME_PATTERNS = [
        r'^\s*at\s+',
        r'^\s*as\s+of\s+',
    ]
    
    # Patterns to preserve as-is (non-date columns)
    PRESERVE_PATTERNS = [
        r'^\$\s*in\s*(millions?|billions?)',
        r'^%\s*change$',
        r'^%$',           # Just % symbol
        r'^change$',      # Just "Change"
        r'^total$',
        r'^average$',
        r'^high$',
        r'^low$',
        r'^period\s+end$',
        r'^inflows?$',
        r'^outflows?$',
        r'^market\s+impact$',
    ]
    
    # Fiscal quarter pattern (e.g., "4Q 2024", "4Q2024")
    FISCAL_QUARTER_PATTERN = r'^(\d)Q\s*(20\d{2})$'
    
    # Combined date pattern
    COMBINED_DATE_PATTERN = r'(at|as\s+of)\s+(\w+)\s+(\d+),?\s*(20\d{2})\s+and\s+(\w+)\s+(\d+),?\s*(20\d{2})'
    
    @classmethod
    def normalize_multi_row_headers(
        cls,
        header_rows: List[List[str]],
        source_filename: str = ''
    ) -> Dict[str, any]:
        """
        Normalize multi-row headers into standardized codes.
        
        Args:
            header_rows: List of header rows (top to bottom), each row is a list of cell values
            source_filename: Source filename for 10-K detection
            
        Returns:
            Dict with:
                'normalized_headers': List of normalized column headers
                'l1_headers': List of L1 headers (main headers)
                'l2_headers': List of period type headers
                'l3_headers': List of year/date headers
                'original_rows': Original rows for reference
        """
        if not header_rows:
            return {
                'normalized_headers': [],
                'l1_headers': [],
                'l2_headers': [],
                'l3_headers': [],
                'original_rows': [],
            }
        
        # Determine number of columns
        num_cols = max(len(row) for row in header_rows)
        
        # Build context for each column
        col_contexts = []
        for col_idx in range(num_cols):
            ctx = cls._build_column_context(header_rows, col_idx)
            col_contexts.append(ctx)
        
        # Propagate spanning header context to columns with empty headers
        cls._propagate_spanning_context(col_contexts, header_rows)
        
        # Generate normalized headers
        normalized = []
        l1_headers = []
        l2_headers = []
        l3_headers = []
        
        for ctx in col_contexts:
            norm, l1, l2, l3 = cls._normalize_column_context(ctx, source_filename)
            normalized.append(norm)
            l1_headers.append(l1)
            l2_headers.append(l2)
            l3_headers.append(l3)
        
        return {
            'normalized_headers': normalized,
            'l1_headers': l1_headers,
            'l2_headers': l2_headers,
            'l3_headers': l3_headers,
            'original_rows': header_rows,
        }
    
    @classmethod
    def _build_column_context(cls, header_rows: List[List[str]], col_idx: int) -> ColumnContext:
        """Build context by analyzing all values in a column across header rows."""
        ctx = ColumnContext()
        
        for row in header_rows:
            if col_idx >= len(row):
                continue
            val = str(row[col_idx]).strip() if row[col_idx] is not None else ''
            if not val or val.lower() == 'nan':
                continue
            
            ctx.raw_values.append(val)
            val_lower = val.lower()
            
            # Check if this is a preserve-as-is column
            if cls._should_preserve(val):
                ctx.is_date_column = False
                continue
            
            # Check for fiscal quarter pattern (4Q 2024)
            fiscal_match = re.match(cls.FISCAL_QUARTER_PATTERN, val.strip(), re.IGNORECASE)
            if fiscal_match:
                ctx.year = fiscal_match.group(2)
                ctx.period_type = f"{fiscal_match.group(1)}Q"  # Store as "4Q"
                continue
            
            # Check for combined dates
            combined_match = re.search(cls.COMBINED_DATE_PATTERN, val_lower, re.IGNORECASE)
            if combined_match:
                ctx.period_type = 'COMBINED'
                ctx.raw_values.append(val)  # Store full combined string
                continue
            
            # Check for period type
            for pattern, period_code in cls.PERIOD_PATTERNS:
                if re.search(pattern, val_lower):
                    ctx.period_type = period_code
                    # Also try to extract month from same cell
                    month = cls._extract_month(val_lower)
                    if month:
                        ctx.month = month
                    break
            
            # Check for point-in-time
            for pattern in cls.POINT_IN_TIME_PATTERNS:
                if re.match(pattern, val_lower):
                    ctx.period_type = 'POINT'
                    # Extract month and year from same cell
                    month = cls._extract_month(val_lower)
                    if month:
                        ctx.month = month
                    year = cls._extract_year(val)
                    if year:
                        ctx.year = year
                    break
            
            # Check for month name (could be in separate row like "March 31,")
            if not ctx.month:
                month = cls._extract_month(val_lower)
                if month:
                    ctx.month = month
            
            # Check for year only
            if not ctx.year:
                year = cls._extract_year(val)
                if year:
                    ctx.year = year
            
            # Check for category (non-date values that aren't special patterns)
            if not cls._is_date_related(val) and not cls._should_preserve(val):
                # Could be a category like "Trading", "IS", "WM"
                if len(val) <= 50 and not re.match(r'^\d+$', val):
                    if not ctx.category:
                        ctx.category = val
                    elif ctx.l1_header == '':
                        ctx.l1_header = ctx.category
                        ctx.category = val
        
        return ctx
    
    @classmethod
    def _propagate_spanning_context(cls, contexts: List[ColumnContext], header_rows: List[List[str]]) -> None:
        """
        Propagate spanning header context to columns with empty/missing values.
        
        For tables like:
            | Three Months Ended |        | Six Months Ended |        |
            | March 31,          |        | June 30,         |        |
            | 2023               | 2024   | 2023             | 2024   |
            
        Each period group should get its own month from row 1.
        """
        # Track spanning context per row
        for row_idx, row in enumerate(header_rows):
            current_period = ''
            current_month = ''
            current_l1 = ''
            current_category = ''
            
            for col_idx in range(len(contexts)):
                ctx = contexts[col_idx]
                cell_val = str(row[col_idx]).strip() if col_idx < len(row) and row[col_idx] else ''
                cell_lower = cell_val.lower() if cell_val else ''
                
                # Check if this cell has period info - UPDATE current values
                period_found = False
                for pattern, period_code in cls.PERIOD_PATTERNS:
                    if re.search(pattern, cell_lower):
                        current_period = period_code
                        # RESET month when new period starts - it will come from next row
                        current_month = ''
                        month = cls._extract_month(cell_lower)
                        if month:
                            current_month = month
                        period_found = True
                        break
                
                # Check for point-in-time - RESET month for new date
                if not period_found and (re.match(r'^\s*at\s+', cell_lower) or re.match(r'^\s*as\s+of\s+', cell_lower)):
                    current_period = 'POINT'
                    current_month = ''  # Reset
                    month = cls._extract_month(cell_lower)
                    if month:
                        current_month = month
                        # Also update year for point-in-time
                        year = cls._extract_year(cell_val)
                        if year and not ctx.year:
                            ctx.year = year
                
                # Check for month in separate row (like "March 31,")
                # Only update if cell has content
                if cell_val and not cls._should_preserve(cell_val):
                    month = cls._extract_month(cell_lower)
                    if month:
                        current_month = month
                
                # Track L1 headers 
                if cell_val and not cls._is_date_related(cell_val) and not cls._should_preserve(cell_val):
                    if row_idx == 0:  # First row often contains L1 headers
                        current_l1 = cell_val
                
                # Track category (row with sub-columns like Trading, IS, WM)
                if row_idx > 0 and cell_val and not cls._is_date_related(cell_val) and not cls._should_preserve(cell_val):
                    current_category = cell_val
                
                # ALWAYS propagate current context to this column if it's missing
                if not ctx.period_type and current_period:
                    ctx.period_type = current_period
                if not ctx.month and current_month:
                    ctx.month = current_month
                if not ctx.l1_header and current_l1:
                    ctx.l1_header = current_l1
                if not ctx.category and current_category:
                    ctx.category = current_category
    
    @classmethod
    def _normalize_column_context(
        cls, 
        ctx: ColumnContext, 
        source_filename: str
    ) -> Tuple[str, str, str, str]:
        """
        Convert column context to normalized header.
        
        Returns:
            Tuple of (normalized_header, l1_header, l2_header, l3_header)
        """
        # Handle non-date columns
        if not ctx.is_date_column:
            clean_vals = [v for v in ctx.raw_values if v and v.lower() != 'nan']
            if not clean_vals:
                return '', '', '', ''
            
            # Special case: combine '%' + 'Change' or similar patterns
            if len(clean_vals) == 2:
                combined_lower = ' '.join(v.lower() for v in clean_vals)
                # Only combine if it forms a known pattern
                if combined_lower in ['% change', 'change %']:
                    return '% change', '', '', '% change'
            
            # Default: return first preserve-pattern value, or first value
            for val in clean_vals:
                if cls._should_preserve(val):
                    return val.lower(), '', '', val.lower()
            return clean_vals[0].lower() if clean_vals else '', '', '', ''
        
        # Handle fiscal quarter (4Q 2024)
        if ctx.period_type and re.match(r'^\dQ$', ctx.period_type):
            code = f"{ctx.period_type}-{ctx.year}" if ctx.year else ctx.period_type
            return code, '', ctx.period_type, ctx.year
        
        # Handle combined dates
        if ctx.period_type == 'COMBINED':
            # Parse combined dates from raw values
            for val in ctx.raw_values:
                match = re.search(cls.COMBINED_DATE_PATTERN, val.lower(), re.IGNORECASE)
                if match:
                    m1, y1 = match.group(2), match.group(4)
                    m2, y2 = match.group(5), match.group(7)
                    q1 = cls.MONTH_TO_QUARTER.get(m1.lower(), 'Q4')
                    q2 = cls.MONTH_TO_QUARTER.get(m2.lower(), 'Q4')
                    code = f"{q1}-{y1} & {q2}-{y2}"
                    if ctx.category:
                        code = f"{code} {ctx.category}"
                    return code, ctx.l1_header, '', code
        
        # Build quarter from month
        quarter = ''
        if ctx.month:
            quarter = cls.MONTH_TO_QUARTER.get(ctx.month.lower(), '')
        
        if not quarter and not ctx.year:
            # Can't normalize - return original or category
            if ctx.category:
                return ctx.category, ctx.l1_header, '', ctx.category
            return ctx.raw_values[0] if ctx.raw_values else '', '', '', ''
        
        # Build normalized code
        code = ''
        l2_value = ''
        
        if ctx.period_type == 'POINT':
            # Point-in-time: Q1-2024
            code = f"{quarter}-{ctx.year}" if quarter and ctx.year else ''
            l2_value = ''
        elif ctx.period_type == 'QTD':
            # Three Months Ended: Q1-QTD-2024
            code = f"{quarter}-QTD-{ctx.year}" if quarter and ctx.year else ''
            l2_value = 'Three Months Ended'
        elif ctx.period_type == 'YTD':
            # Six/Nine Months Ended: Q2-YTD-2024 or Q3-YTD-2024
            code = f"{quarter}-YTD-{ctx.year}" if quarter and ctx.year else ''
            l2_value = 'Six Months Ended' if quarter == 'Q2' else 'Nine Months Ended'
        elif ctx.period_type == 'ANNUAL':
            # Year Ended: YTD-2024
            code = f"YTD-{ctx.year}" if ctx.year else ''
            l2_value = 'Year Ended'
        elif ctx.year:
            # Year only - check if 10-K
            is_10k = '10k' in source_filename.lower() if source_filename else False
            if is_10k:
                code = f"YTD-{ctx.year}"
            else:
                code = f"{quarter}-{ctx.year}" if quarter else ctx.year
        
        # Clean category (remove nan)
        clean_category = ctx.category if ctx.category and ctx.category.lower() != 'nan' else ''
        
        # Append category if present
        if clean_category and code:
            code = f"{code} {clean_category}"
        
        return code, ctx.l1_header, l2_value, ctx.year
    
    @classmethod
    def _extract_month(cls, text: str) -> str:
        """Extract month name from text."""
        text_lower = text.lower()
        for month in cls.MONTH_TO_QUARTER.keys():
            if month in text_lower:
                # Return full month name for consistency
                full_names = {
                    'jan': 'january', 'feb': 'february', 'mar': 'march',
                    'apr': 'april', 'jun': 'june', 'jul': 'july',
                    'aug': 'august', 'sep': 'september', 'sept': 'september',
                    'oct': 'october', 'nov': 'november', 'dec': 'december',
                }
                return full_names.get(month, month)
        return ''
    
    @classmethod
    def _extract_year(cls, text: str) -> str:
        """Extract 4-digit year from text."""
        match = re.search(r'(20\d{2})', str(text))
        return match.group(1) if match else ''
    
    @classmethod
    def _is_date_related(cls, text: str) -> bool:
        """Check if text contains date-related content."""
        text_lower = text.lower()
        
        # Check for year
        if re.search(r'20\d{2}', text):
            return True
        
        # Check for month
        for month in cls.MONTH_TO_QUARTER.keys():
            if month in text_lower:
                return True
        
        # Check for period keywords
        date_keywords = ['ended', 'at', 'as of', 'months', 'year', 'quarter', 'fiscal']
        for kw in date_keywords:
            if kw in text_lower:
                return True
        
        return False
    
    @classmethod
    def _should_preserve(cls, text: str) -> bool:
        """Check if text should be preserved as-is (non-date column)."""
        text_lower = text.lower().strip()
        for pattern in cls.PRESERVE_PATTERNS:
            if re.match(pattern, text_lower, re.IGNORECASE):
                return True
        return False
    
    @classmethod
    def normalize_single_header(cls, header: str, source_filename: str = '') -> str:
        """
        Normalize a single column header string.
        
        Convenience method for single-row headers.
        """
        result = cls.normalize_multi_row_headers([[header]], source_filename)
        return result['normalized_headers'][0] if result['normalized_headers'] else header


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def normalize_headers(header_rows: List[List[str]], source: str = '') -> Dict:
    """Normalize multi-row headers. Convenience wrapper."""
    return MultiRowHeaderNormalizer.normalize_multi_row_headers(header_rows, source)


def normalize_header(header: str, source: str = '') -> str:
    """Normalize a single header string. Convenience wrapper."""
    return MultiRowHeaderNormalizer.normalize_single_header(header, source)
