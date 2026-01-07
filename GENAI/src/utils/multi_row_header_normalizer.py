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
                    # Strip footnote markers from category names
                    clean_val = cls._strip_footnote_marker(val)
                    if not ctx.category:
                        ctx.category = clean_val
                    elif ctx.l1_header == '':
                        ctx.l1_header = ctx.category
                        ctx.category = clean_val
        
        return ctx
    
    @classmethod
    def _propagate_spanning_context(cls, contexts: List[ColumnContext], header_rows: List[List[str]]) -> None:
        """
        Propagate spanning header context to columns with empty/missing values.
        
        For tables like:
            |               | Three Months Ended September 30, 2025 |       |       |       |       |
            | $ in millions | Trading         | Fees 1 | Net Int | All Other | Total |
            
        ALL columns under "Three Months Ended" should get the same period/month context.
        """
        if not header_rows or not contexts:
            return
        
        # FIRST PASS: For each row, track spans of period/date headers
        # A span starts at a cell with period info and continues until next period or end
        
        for row_idx, row in enumerate(header_rows):
            current_period = ''
            current_month = ''
            current_year = ''
            span_start_col = -1
            
            for col_idx in range(len(row)):
                cell_val = str(row[col_idx]).strip() if col_idx < len(row) and row[col_idx] else ''
                cell_lower = cell_val.lower() if cell_val else ''
                
                if not cell_val:
                    # Empty cell - continue current span
                    continue
                
                # Check if this cell starts a NEW period span
                period_found = ''
                for pattern, period_code in cls.PERIOD_PATTERNS:
                    if re.search(pattern, cell_lower):
                        period_found = period_code
                        break
                
                # Check for point-in-time
                if not period_found:
                    if re.match(r'^\s*at\s+', cell_lower) or re.match(r'^\s*as\s+of\s+', cell_lower):
                        period_found = 'POINT'
                
                if period_found:
                    # NEW span starts here
                    current_period = period_found
                    current_month = cls._extract_month(cell_lower)
                    current_year = cls._extract_year(cell_val)
                    span_start_col = col_idx
                    
                    # Apply to this column's context
                    if col_idx < len(contexts):
                        ctx = contexts[col_idx]
                        if not ctx.period_type:
                            ctx.period_type = current_period
                        if not ctx.month and current_month:
                            ctx.month = current_month
                        if not ctx.year and current_year:
                            ctx.year = current_year
                else:
                    # If current span is active and this cell has content,
                    # propagate span context to this column
                    if current_period and col_idx < len(contexts):
                        ctx = contexts[col_idx]
                        if not ctx.period_type:
                            ctx.period_type = current_period
                        if not ctx.month and current_month:
                            ctx.month = current_month
                        if not ctx.year and current_year:
                            ctx.year = current_year
        
        # SECOND PASS: Propagate period, month, year, AND category from previous columns if still missing
        # This handles cases where column 2 has the period but columns 3,4,5 need it too
        last_period = ''
        last_month = ''
        last_year = ''
        last_category = ''  # Track spanning category headers like "Average Monthly Balance"
        
        for ctx in contexts:
            # Update tracking when we see a column with period/month/year/category
            if ctx.period_type:
                last_period = ctx.period_type
            if ctx.month:
                last_month = ctx.month
            if ctx.year:
                last_year = ctx.year
            # Track category from ANY column that has one (including date columns)
            # This allows categories like "Average Monthly Balance" to propagate even when
            # combined with a year in the same column
            if ctx.category:
                last_category = ctx.category
            
            # Propagate to columns that have categories but no period/month/year
            if ctx.category and not ctx.period_type and last_period:
                ctx.period_type = last_period
            if ctx.category and not ctx.month and last_month:
                ctx.month = last_month
            if ctx.category and not ctx.year and last_year:
                ctx.year = last_year
            
            # ALSO propagate to columns that have ONLY a year but no period
            # This handles "2024" columns following "Three Months Ended March 31, 2025"
            if ctx.year and not ctx.period_type and last_period:
                ctx.period_type = last_period
            if ctx.year and not ctx.month and last_month:
                ctx.month = last_month
            
            # PROPAGATE CATEGORY: If this column has a year but no category,
            # inherit the spanning category from earlier columns
            # This handles: [Average Monthly Balance, '', '', ''] + [$ in millions, 2024, 2023, 2022]
            # Where columns 1-3 should become "YTD-2024 Average Monthly Balance"
            if ctx.year and not ctx.category and last_category:
                ctx.category = last_category
            
            # DYNAMIC FIX: Also propagate to NON-DATE columns (preserve patterns like 'Average', 'High')
            # These are columns where is_date_column=False but have raw values
            if not ctx.is_date_column and ctx.raw_values and last_period:
                if not ctx.period_type:
                    ctx.period_type = last_period
                if not ctx.month and last_month:
                    ctx.month = last_month
                if not ctx.year and last_year:
                    ctx.year = last_year
    
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
            
            # Get the preserve value
            preserve_val = None
            for val in clean_vals:
                if cls._should_preserve(val):
                    preserve_val = val.lower()
                    break
            if not preserve_val:
                preserve_val = clean_vals[0].lower() if clean_vals else ''
            
            # DYNAMIC FIX: If this column has date context from spanning header,
            # prefix the preserve value with Q-code
            if preserve_val and ctx.period_type and ctx.month and ctx.year:
                quarter = cls.MONTH_TO_QUARTER.get(ctx.month.lower(), '')
                if quarter:
                    if ctx.period_type == 'QTD':
                        code = f"{quarter}-QTD-{ctx.year}"
                    elif ctx.period_type == 'YTD':
                        code = f"{quarter}-YTD-{ctx.year}"
                    elif ctx.period_type == 'POINT':
                        code = f"{quarter}-{ctx.year}"
                    else:
                        code = f"{quarter}-{ctx.year}"
                    # Capitalize preserve value nicely
                    nice_val = preserve_val.title()
                    return f"{code} {nice_val}", '', '', code
            
            return preserve_val, '', '', preserve_val
        
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
            # Can't normalize - return original or category (with footnote stripped)
            if ctx.category:
                cleaned = cls._dedupe_repeated_words(ctx.category)
                return cleaned, ctx.l1_header, '', cleaned
            if ctx.raw_values:
                # Strip footnotes from passthrough values
                cleaned = cls._strip_footnote_marker(ctx.raw_values[0])
                cleaned = cls._dedupe_repeated_words(cleaned)
                return cleaned, '', '', ''
            return '', '', '', ''
        
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
        
        # Clean category (remove nan and strip footnotes)
        clean_category = ctx.category if ctx.category and ctx.category.lower() != 'nan' else ''
        
        # Append category if present
        if clean_category and code:
            code = f"{code} {clean_category}"
        
        # Deduplicate repeated words (e.g., "Q3-2025 AAA AAA" -> "Q3-2025 AAA")
        code = cls._dedupe_repeated_words(code)
        
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
    def _strip_footnote_marker(cls, text: str) -> str:
        """Remove trailing footnote markers like ' 1', ' 2', ' 3' from text.
        
        Preserves meaningful numbered categories:
        - 'Level 1', 'Level 2', 'Level 3' - keep the numbers
        - 'Tier 1', 'Tier 2' - keep the numbers
        - 'Netting 1' - footnote, strip it
        - 'Fees 1', 'Net Interest 2' - footnotes, strip them
        """
        text = text.strip()
        
        # Patterns where trailing numbers are MEANINGFUL (not footnotes)
        preserve_patterns = [
            r'^Level\s+\d+$',      # Level 1, Level 2, Level 3
            r'^Tier\s+\d+$',       # Tier 1, Tier 2
            r'^Type\s+\d+$',       # Type 1, Type 2
            r'^Class\s+\d+$',      # Class 1, Class 2
            r'^Category\s+\d+$',   # Category 1, Category 2
        ]
        
        for pattern in preserve_patterns:
            if re.match(pattern, text, re.IGNORECASE):
                return text  # Keep the number
        
        # Otherwise strip trailing footnote markers
        return re.sub(r'\s+\d+$', '', text)
    
    @classmethod
    def _dedupe_repeated_words(cls, text: str) -> str:
        """Remove consecutive duplicate words from text.
        
        Examples:
            'Q3-2025 AAA AAA' -> 'Q3-2025 AAA'
            'total Total' -> 'total'
            'Q3-2025 Level Level 1' -> 'Q3-2025 Level 1'
        """
        if not text:
            return text
        
        words = text.split()
        result = []
        prev_word = None
        
        for word in words:
            # Case-insensitive comparison for deduplication
            if prev_word is None or word.lower() != prev_word.lower():
                result.append(word)
                prev_word = word
        
        return ' '.join(result)
    
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
