"""
Column Header Normalizer - Replace date headers with Year/Quarter codes.

Standalone module for normalizing column headers with date patterns.
Used by: process.py, consolidated_exporter.py
"""

import re
import pandas as pd
from typing import Dict, List, Tuple


class ColumnHeaderNormalizer:
    """
    Normalize column headers by replacing date patterns with Year/Quarter codes.
    
    Handles multi-row headers where period type and year are in separate rows.
    
    Examples:
        Scenario 1 (single row dates):
        ['At March 31, 2024', 'At December 31, 2020'] → ['Q1-2024', 'Q4-2020']
        
        Scenario 2 (period + year in separate rows):
        Row 1: ['', 'Three Months Ended March 31,', 'Six Months Ended June 30,']
        Row 2: ['$ in millions', '2020', '2024']
        → ['$ in millions', 'Q1-QTD-2020', 'Q2-YTD-2024']
        
        Scenario 3 (L1 + period + year):
        Row 1: ['', 'Average Monthly Balance']
        Row 2: ['', 'Three Months Ended March 31,']
        Row 3: ['$ in millions', '2019', '2024', '2023']
        → Row 1: ['', 'Average Monthly Balance']
           Final: ['$ in millions', 'Q1-QTD-2019', 'Q1-QTD-2024', 'Q1-QTD-2023']
    """
    
    # Patterns that indicate period type (L2)
    PERIOD_TYPE_PATTERNS = [
        ('three months ended', 'QTD'),
        ('six months ended', 'YTD'),
        ('nine months ended', 'YTD'),
        ('year ended', 'YTD'),
    ]
    
    # Patterns that indicate point-in-time dates (L3 only)
    DATE_PATTERNS = [
        r'at\s+(\w+)\s+\d+,?\s*(20\d{2})',        # At March 31, 2024
        r'as of\s+(\w+)\s+\d+,?\s*(20\d{2})',     # As of March 31, 2024
    ]
    
    # Full period + date patterns (captures period type and date together)
    FULL_PERIOD_PATTERNS = [
        (r'three months ended\s+(\w+)\s+\d+,?\s*(20\d{2})', 'QTD'),    # Three Months Ended March 31, 2024
        (r'six months ended\s+(\w+)\s+\d+,?\s*(20\d{2})', 'YTD'),      # Six Months Ended June 30, 2024
        (r'nine months ended\s+(\w+)\s+\d+,?\s*(20\d{2})', 'YTD'),     # Nine Months Ended September 30, 2024
        (r'year ended\s+(\w+)\s+\d+,?\s*(20\d{2})', 'ANNUAL'),         # Year Ended December 31, 2023 → YTD-2023
    ]
    
    # Non-date patterns to preserve as-is
    PRESERVE_PATTERNS = [
        r'^\$\s*in\s*(millions?|billions?)$',   # $ in millions
        r'^total$',
        r'^average$',
        r'^corporate$',
        r'^other$',
    ]
    
    # Month to quarter mapping
    MONTH_TO_QUARTER = {
        'january': 'Q1', 'february': 'Q1', 'march': 'Q1',
        'april': 'Q2', 'may': 'Q2', 'june': 'Q2',
        'july': 'Q3', 'august': 'Q3', 'september': 'Q3',
        'october': 'Q4', 'november': 'Q4', 'december': 'Q4',
    }
    
    @classmethod
    def normalize_headers(
        cls,
        header_rows: list,
        source_filename: str = ''
    ) -> dict:
        """
        Normalize column headers by replacing date patterns with Year/Quarter codes.
        
        Args:
            header_rows: List of header rows, each row is a list of cell values
                         Example: [['', 'Three Months Ended March 31,'], ['$ in millions', '2020']]
            source_filename: Source filename for 10-K detection
                         
        Returns:
            Dict with:
                'normalized_headers': List of normalized column headers (final row)
                'l1_headers': List of L1 headers (category/main header like 'Average Monthly Balance')
                'original_rows': Original header rows for reference
        """
        result = {
            'normalized_headers': [],
            'l1_headers': [],
            'original_rows': header_rows,
        }
        
        if not header_rows:
            return result
        
        # Determine number of columns
        num_cols = max(len(row) for row in header_rows) if header_rows else 0
        
        # Pre-scan for spanning headers to track context
        # Spanning headers often appear in row 0 (R13) and span multiple columns
        spanning_context = {}  # col_idx -> (quarter, period_type)
        current_quarter = None
        current_period = None
        
        # First pass: identify spanning headers and their context
        if len(header_rows) > 0:
            for col_idx in range(num_cols):
                val = str(header_rows[0][col_idx]).strip().lower() if col_idx < len(header_rows[0]) and header_rows[0][col_idx] else ''
                
                # Check if this is a period+month spanning header
                for pattern, period_code in cls.PERIOD_TYPE_PATTERNS:
                    if pattern in val:
                        # Found period type, extract quarter
                        for month, q in cls.MONTH_TO_QUARTER.items():
                            if month in val:
                                current_quarter = q
                                current_period = period_code
                                break
                        break
                
                # Store context for this column
                if current_quarter:
                    spanning_context[col_idx] = (current_quarter, current_period)
        
        # Second pass: normalize each column with context inheritance
        for col_idx in range(num_cols):
            # Get all values for this column from all rows
            col_values = []
            for row in header_rows:
                val = str(row[col_idx]).strip() if col_idx < len(row) and row[col_idx] else ''
                col_values.append(val)
            
            # Get inherited context for year-only values
            inherited_context = spanning_context.get(col_idx)
            
            # Analyze and normalize this column
            normalized, l1 = cls._normalize_column(col_values, source_filename, inherited_context)
            result['normalized_headers'].append(normalized)
            result['l1_headers'].append(l1)
        
        return result
    
    @classmethod
    def _normalize_column(cls, col_values: list, source_filename: str = '', inherited_context: tuple = None) -> Tuple[str, str]:
        """
        Normalize a single column's header values.
        
        Args:
            col_values: List of values from top to bottom for this column
            source_filename: Source filename for 10-K detection
            inherited_context: Tuple of (quarter, period_type) from spanning header
            
        Returns:
            Tuple of (normalized_header, l1_header)
        """
        l1_header = ''
        period_type = ''
        year = ''
        quarter = ''
        trailing_text = ''  # Preserve text after date
        
        # Initialize from inherited context (for year-only values under spanning headers)
        if inherited_context:
            quarter, period_type = inherited_context
        
        # Abbreviated month mapping
        ABBREV_MONTHS = {
            'jan': 'january', 'feb': 'february', 'mar': 'march',
            'apr': 'april', 'may': 'may', 'jun': 'june',
            'jul': 'july', 'aug': 'august', 'sep': 'september',
            'oct': 'october', 'nov': 'november', 'dec': 'december',
        }
        
        # Clean values
        clean_values = []
        for v in col_values:
            v_clean = str(v).strip() if v else ''
            if v_clean.lower() not in ['nan', 'none', '']:
                clean_values.append(v_clean)
        
        if not clean_values:
            return '', ''
        
        # Check if this is a preserve-as-is column
        combined = ' '.join(clean_values)
        combined_lower = combined.lower()
        
        for pattern in cls.PRESERVE_PATTERNS:
            if re.match(pattern, combined_lower, re.IGNORECASE):
                return combined, ''
        
        # First column often is '$ in millions' - preserve it
        if len(col_values) > 0:
            first_val = str(col_values[-1]).strip() if col_values[-1] else ''
            if first_val.lower() in ['$ in millions', '$ in billions']:
                return first_val, ''
        
        # === Check FULL_PERIOD_PATTERNS first (e.g., "Three Months Ended June 30, 2024") ===
        for val in clean_values:
            val_lower = val.lower()
            for pattern, period_code in cls.FULL_PERIOD_PATTERNS:
                match = re.search(pattern, val_lower, re.IGNORECASE)
                if match:
                    detected_month = match.group(1).lower()
                    # Handle abbreviated months
                    if detected_month in ABBREV_MONTHS:
                        detected_month = ABBREV_MONTHS[detected_month]
                    detected_year = match.group(2)
                    if detected_month in cls.MONTH_TO_QUARTER:
                        quarter = cls.MONTH_TO_QUARTER[detected_month]
                        year = detected_year
                        period_type = period_code
                        # Extract trailing text after the pattern
                        full_match = re.search(pattern, val_lower, re.IGNORECASE)
                        if full_match and full_match.end() < len(val):
                            trailing_text = val[full_match.end():].strip()
                        
                        # Build code - ANNUAL is special case (Year Ended → YTD-YEAR)
                        if period_code == 'ANNUAL':
                            code = f"YTD-{year}"
                        else:
                            code = f"{quarter}-{period_code}-{year}"
                        
                        if trailing_text:
                            code = f"{code} {trailing_text}"
                        return code, l1_header
        
        # === Analyze each value for other patterns ===
        for val in clean_values:
            val_lower = val.lower()
            
            # Check for period type (but only period, not full date)
            for pattern, period_code in cls.PERIOD_TYPE_PATTERNS:
                if pattern in val_lower:
                    period_type = period_code
                    # Extract month from period type string
                    for m in cls.MONTH_TO_QUARTER:
                        if m in val_lower:
                            quarter = cls.MONTH_TO_QUARTER[m]
                            break
                    # Also check abbreviated months
                    for abbrev, full in ABBREV_MONTHS.items():
                        if abbrev in val_lower.split():
                            quarter = cls.MONTH_TO_QUARTER[full]
                            break
                    break
            
            # Check for point-in-time date (At/As of) - with optional day number
            # Pattern: At/As of Month [Day,] Year [trailing]
            for date_pattern in cls.DATE_PATTERNS:
                match = re.search(date_pattern, val_lower, re.IGNORECASE)
                if match:
                    detected_month = match.group(1).lower()
                    # Handle abbreviated months
                    if detected_month in ABBREV_MONTHS:
                        detected_month = ABBREV_MONTHS[detected_month]
                    detected_year = match.group(2)
                    if detected_month in cls.MONTH_TO_QUARTER:
                        quarter = cls.MONTH_TO_QUARTER[detected_month]
                        year = detected_year
                        period_type = ''  # Point-in-time, no QTD/YTD
                        # Extract trailing text
                        if match.end() < len(val):
                            trailing_text = val[match.end():].strip()
                    break
            
            # Check for "At Month Year" pattern (no day number)
            no_day_match = re.search(r'at\s+(\w+)\s+(20\d{2})', val_lower, re.IGNORECASE)
            if no_day_match and not year:
                detected_month = no_day_match.group(1).lower()
                if detected_month in ABBREV_MONTHS:
                    detected_month = ABBREV_MONTHS[detected_month]
                detected_year = no_day_match.group(2)
                if detected_month in cls.MONTH_TO_QUARTER:
                    quarter = cls.MONTH_TO_QUARTER[detected_month]
                    year = detected_year
                    period_type = ''
                    if no_day_match.end() < len(val):
                        trailing_text = val[no_day_match.end():].strip()
            
            # Check for year only
            if re.match(r'^20\d{2}$', val.strip()):
                year = val.strip()
            
            # Check for L1 (category like 'Average Monthly Balance')
            has_date = any(m in val_lower for m in cls.MONTH_TO_QUARTER.keys())
            has_abbrev = any(abbrev in val_lower.split() for abbrev in ABBREV_MONTHS.keys())
            has_period = any(p[0] in val_lower for p in cls.PERIOD_TYPE_PATTERNS)
            if not has_date and not has_abbrev and not has_period and not re.match(r'^20\d{2}$', val.strip()):
                if val.lower() not in ['$ in millions', '$ in billions', 'nan', 'none', '']:
                    l1_header = val
        
        # Build the normalized code
        if year:
            if period_type:
                # QTD or YTD with period type
                code = f"{quarter}-{period_type}-{year}"
            elif quarter:
                # Point-in-time
                code = f"{quarter}-{year}"
            else:
                # Year only (10-K style)
                code = f"YTD-{year}"
            
            # Append trailing text if present
            if trailing_text:
                code = f"{code} {trailing_text}"
            return code, l1_header
        
        # No year found - return original combined value
        return combined, l1_header
    
    @classmethod
    def normalize_dataframe_headers(
        cls,
        df: 'pd.DataFrame',
        num_header_rows: int = 1,
        source_filename: str = ''
    ) -> 'pd.DataFrame':
        """
        Normalize column headers in a DataFrame.
        
        Args:
            df: DataFrame with headers to normalize
            num_header_rows: Number of rows at top that are headers (default: 1)
            source_filename: Source filename for 10-K detection
            
        Returns:
            DataFrame with normalized headers
        """
        if df.empty or num_header_rows < 1:
            return df
        
        # Extract header rows
        header_rows = []
        for i in range(min(num_header_rows, len(df))):
            row = df.iloc[i].tolist()
            header_rows.append(row)
        
        # Normalize
        result = cls.normalize_headers(header_rows, source_filename)
        
        # Replace the last header row with normalized values
        if result['normalized_headers']:
            # Create new DataFrame with normalized headers
            data_rows = df.iloc[num_header_rows:].values.tolist() if len(df) > num_header_rows else []
            
            # Build new header rows
            new_header_rows = header_rows[:-1] if len(header_rows) > 1 else []
            new_header_rows.append(result['normalized_headers'])
            
            # Combine
            all_rows = new_header_rows + data_rows
            new_df = pd.DataFrame(all_rows)
            new_df.columns = df.columns[:len(new_df.columns)] if len(df.columns) >= len(new_df.columns) else range(len(new_df.columns))
            
            return new_df
        
        return df
