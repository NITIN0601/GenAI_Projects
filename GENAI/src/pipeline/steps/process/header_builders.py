"""
Header builders for the Process step.

Functions for building combined headers from multi-level header rows.
"""

import re
from typing import List, Optional

from src.utils import get_logger
from src.utils.header_processor import HeaderProcessor
from src.pipeline.steps.process.table_finder import find_first_data_row_after_source

logger = get_logger(__name__)


def cleanup_headers(headers: List[str]) -> List[str]:
    """
    Clean up combined headers by removing duplicates and footnotes.
    
    - Removes consecutive duplicate words (e.g., 'AAA AAA' -> 'AAA')
    - Strips trailing footnote markers (e.g., ' 1' from 'Netting 1')
    - Preserves meaningful numbers like 'Level 1', 'Tier 1'
    
    Args:
        headers: List of header strings
        
    Returns:
        Cleaned list of headers
    """
    cleaned = []
    for h in headers:
        if not h:
            cleaned.append('')
            continue
        
        h = str(h)
        
        # Dedupe consecutive repeated words (case-insensitive)
        words = h.split()
        deduped = []
        prev_word = None
        for word in words:
            if prev_word is None or word.lower() != prev_word.lower():
                deduped.append(word)
                prev_word = word
        h = ' '.join(deduped)
        
        # Strip trailing footnote markers (but preserve Level 1, Tier 1, etc.)
        preserve_patterns = [
            r'\bLevel\s+\d+$',
            r'\bTier\s+\d+$',
            r'\bType\s+\d+$',
        ]
        should_strip = True
        for pattern in preserve_patterns:
            if re.search(pattern, h, re.IGNORECASE):
                should_strip = False
                break
        
        if should_strip:
            h = re.sub(r'\s+\d+$', '', h)
        
        cleaned.append(h)
    
    return cleaned


def build_combined_headers_3level(
    header_rows_data: List[List], 
    normalized_headers: List[str], 
    num_cols: int
) -> List[str]:
    """
    Build combined headers for 3-level patterns.
    
    Pattern: Period/Date (L1) + Year/Date (L2) + Category (L3)
    Output: "Q3-2025 Level 2 | Q3-2025 Level 3 | Q3-2025 Total"
    
    Key: Propagate the date code across ALL category columns.
    
    Args:
        header_rows_data: List of lists containing header row values
        normalized_headers: List of normalized header strings
        num_cols: Total number of columns
        
    Returns:
        List of combined header strings
    """
    combined = []
    
    # Find the primary date code from normalized_headers
    primary_date_code = ''
    for norm in normalized_headers:
        if norm and (norm.startswith('Q') or 'YTD' in str(norm) or 'QTD' in str(norm)):
            # Get just the date part (e.g., "Q3-2025" from "Q3-2025 Level 2")
            parts = str(norm).split()
            primary_date_code = parts[0] if parts else norm
            break
    
    # Also try to find date code from header rows
    if not primary_date_code:
        for row_data in header_rows_data:
            for val in row_data:
                if val and str(val).startswith('Q') and '-' in str(val):
                    primary_date_code = str(val).split()[0]
                    break
            if primary_date_code:
                break
    
    # Find the category row (usually the last row with unit indicator in col 1)
    category_row_idx = -1
    for i, row_data in enumerate(header_rows_data):
        if row_data[0] and any(kw in str(row_data[0]).lower() for kw in ['$ in', 'in millions', 'in billions', 'fee rate']):
            category_row_idx = i
    
    # If no category row found, use the last row
    if category_row_idx == -1:
        category_row_idx = len(header_rows_data) - 1
    
    category_row = header_rows_data[category_row_idx] if category_row_idx >= 0 else []
    
    for col_idx in range(num_cols):
        if col_idx == 0:
            # Column 1: Keep unit description from category row
            unit_desc = ''
            for row_data in header_rows_data:
                val = row_data[0] if len(row_data) > 0 else ''
                if val and any(kw in str(val).lower() for kw in ['$ in', 'in millions', 'in billions', 'fee rate']):
                    unit_desc = str(val)
                    break
            combined.append(unit_desc)
        else:
            # Data columns: Combine date code + category
            # Use the column-specific normalized header if available, otherwise use primary date code
            norm_code = normalized_headers[col_idx] if col_idx < len(normalized_headers) and normalized_headers[col_idx] else ''
            
            # If this column has no norm_code, use the primary date code
            if not norm_code:
                norm_code = primary_date_code
            
            # Get the category from the category row
            category = str(category_row[col_idx] if col_idx < len(category_row) and category_row[col_idx] else '').strip()
            
            # Skip category if it looks like a date/year or is a duplicate of norm_code
            if category:
                is_date_pattern = (
                    re.match(r'^20\d{2}$', category) or
                    category.startswith('Q') or
                    'months ended' in category.lower() or
                    category.lower().startswith('at ')
                )
                if is_date_pattern or category == norm_code:
                    category = ''
            
            # Build the combined header
            if norm_code and category:
                # Check if category is already in norm_code to prevent duplicates like "Q3-2025 AAA AAA"
                if category.lower() in norm_code.lower():
                    combined.append(norm_code)
                else:
                    combined.append(f"{norm_code} {category}")
            elif norm_code:
                combined.append(norm_code)
            elif category:
                # Even if no date code, prepend primary if available
                if primary_date_code:
                    combined.append(f"{primary_date_code} {category}")
                else:
                    combined.append(category)
            else:
                combined.append('')
    
    # Final cleanup: dedupe repeated words and strip footnotes
    combined = cleanup_headers(combined)
    
    return combined


def build_combined_headers_4level(
    header_rows_data: List[List], 
    normalized_headers: List[str], 
    num_cols: int
) -> List[str]:
    """
    Build combined headers for 4+ level patterns.
    
    Pattern: Period (L1) + Year (L2) + Year (L3 dup) + Category (L4)
    Output: "Q3-QTD-2025 Amortized Cost | Q3-QTD-2025 % of Loans | Q3-QTD-2024 Amortized Cost | Q3-QTD-2024 % of Loans"
    
    Key: Track year column spans to propagate correct date code to each category column.
    
    Args:
        header_rows_data: List of lists containing header row values
        normalized_headers: List of normalized header strings
        num_cols: Total number of columns
        
    Returns:
        List of combined header strings
    """
    combined = []
    
    # Find year row and build column-to-year mapping
    year_row_idx = -1
    year_row = []
    for i, row_data in enumerate(header_rows_data):
        years_found = sum(1 for v in row_data[1:] if v and re.match(r'^20\d{2}$', str(v).strip()))
        if years_found >= 1:
            year_row_idx = i
            year_row = row_data
            break
    
    # Build column-to-year mapping (propagate year across empty columns)
    col_to_year = {}
    current_year = None
    for col_idx in range(1, num_cols):
        if col_idx < len(year_row):
            val = year_row[col_idx]
            if val and re.match(r'^20\d{2}$', str(val).strip()):
                current_year = str(val).strip()
        if current_year:
            col_to_year[col_idx] = current_year
    
    # Determine period type from first row
    period_text = ' '.join(str(v or '') for v in header_rows_data[0]).lower() if header_rows_data else ''
    
    def build_date_code(year: str) -> str:
        """Build date code based on period type and year."""
        if not year:
            return ''
        if 'three months' in period_text or '3 months' in period_text:
            if 'september' in period_text or 'sept' in period_text:
                return f"Q3-QTD-{year}"
            elif 'june' in period_text:
                return f"Q2-QTD-{year}"
            elif 'march' in period_text:
                return f"Q1-QTD-{year}"
            elif 'december' in period_text:
                return f"Q4-QTD-{year}"
        elif 'six months' in period_text or '6 months' in period_text:
            if 'june' in period_text:
                return f"Q2-YTD-{year}"
            elif 'september' in period_text:
                return f"Q3-YTD-{year}"
        elif 'nine months' in period_text or '9 months' in period_text:
            if 'september' in period_text:
                return f"Q3-YTD-{year}"
        elif 'at ' in period_text or 'as of' in period_text:
            if 'september' in period_text or 'sept' in period_text:
                return f"Q3-{year}"
            elif 'june' in period_text:
                return f"Q2-{year}"
            elif 'march' in period_text:
                return f"Q1-{year}"
            elif 'december' in period_text:
                return f"Q4-{year}"
        return f"Q4-{year}"  # Default
    
    # Find category row (usually has categories like "Amortized Cost", "% of Loans")
    category_row_idx = -1
    for i, row_data in enumerate(header_rows_data):
        non_empty = [str(v).strip() for v in row_data[1:] if v and str(v).strip()]
        if non_empty:
            has_categories = any(
                kw in ' '.join(non_empty).lower() 
                for kw in ['amortized', 'cost', 'value', 'level', 'total', '%', 'fair']
            )
            if has_categories:
                category_row_idx = i
    
    if category_row_idx == -1:
        category_row_idx = len(header_rows_data) - 1
    
    category_row = header_rows_data[category_row_idx] if 0 <= category_row_idx < len(header_rows_data) else []
    
    for col_idx in range(num_cols):
        if col_idx == 0:
            # Column 1: Keep unit description
            unit_desc = ''
            for row_data in header_rows_data:
                val = row_data[0] if len(row_data) > 0 else ''
                if val and any(kw in str(val).lower() for kw in ['$ in', 'in millions', 'in billions', 'fee rate']):
                    unit_desc = str(val)
                    break
            combined.append(unit_desc)
        else:
            # Data columns: Get date code from column-to-year mapping
            year = col_to_year.get(col_idx, '')
            norm_code = ''
            
            # First try normalized_headers
            if col_idx < len(normalized_headers) and normalized_headers[col_idx]:
                norm_code = normalized_headers[col_idx]
            # If no norm_code, build from year
            elif year:
                norm_code = build_date_code(year)
            
            # Get category
            category = str(category_row[col_idx] if col_idx < len(category_row) and category_row[col_idx] else '').strip()
            
            # Skip category if it looks like a date/year
            if category:
                is_date_pattern = (
                    re.match(r'^20\d{2}$', category) or
                    category.startswith('Q') or
                    'months ended' in category.lower()
                )
                if is_date_pattern:
                    category = ''
            
            # Build combined header - ALWAYS prepend date code if we have it
            if norm_code and category:
                # Check if category is already in norm_code to prevent duplicates
                if category.lower() in norm_code.lower():
                    combined.append(norm_code)
                else:
                    combined.append(f"{norm_code} {category}")
            elif norm_code:
                combined.append(norm_code)
            elif category:
                # Still try to get a date code for this column
                if year:
                    date_code = build_date_code(year)
                    combined.append(f"{date_code} {category}")
                else:
                    combined.append(category)
            else:
                combined.append('')
    
    # Final cleanup: dedupe repeated words and strip footnotes
    combined = cleanup_headers(combined)
    
    return combined


def build_flattened_headers(
    ws, 
    header_start: int, 
    data_start: int, 
    num_cols: int, 
    normalized_headers: List[str]
) -> List[str]:
    """
    Build flattened headers by combining values from all header rows.
    
    Logic:
    - For column 1: Find unit description (e.g., "$ in millions") from header rows
    - For data columns: Use normalized headers if available, otherwise combine row values
    
    Args:
        ws: openpyxl Worksheet object
        header_start: Starting row for headers
        data_start: Starting row for data
        num_cols: Total number of columns
        normalized_headers: List of normalized header strings
        
    Returns:
        List of flattened header strings
    """
    flattened = []
    
    for col_idx in range(1, num_cols + 1):
        if col_idx == 1:
            # Column 1: find unit description or row label header
            # Look for patterns like "$ in millions", "$ in billions", "Fee rate in bps"
            col1_value = ''
            for row in range(header_start, data_start):
                val = ws.cell(row, 1).value
                if val:
                    val_str = str(val).strip()
                    # Check if it looks like a unit description
                    val_lower = val_str.lower()
                    if any(kw in val_lower for kw in ['$ in', 'in millions', 'in billions', 'in bps', 'fee rate', 'rate in']):
                        col1_value = val_str
                        break
            
            # If no unit found, use the first non-empty column 1 value from header rows
            if not col1_value:
                for row in range(header_start, data_start):
                    val = ws.cell(row, 1).value
                    if val and str(val).strip():
                        col1_value = str(val).strip()
                        break
            
            flattened.append(col1_value)
        else:
            # Data columns: prefer normalized header, else combine
            idx = col_idx - 1
            if idx < len(normalized_headers) and normalized_headers[idx]:
                flattened.append(normalized_headers[idx])
            else:
                # Combine all header row values for this column
                parts = []
                for row in range(header_start, data_start):
                    val = ws.cell(row, col_idx).value
                    if val and str(val).strip():
                        val_str = str(val).strip()
                        # Skip duplicates
                        if val_str not in parts:
                            parts.append(val_str)
                flattened.append(' '.join(parts) if parts else '')
    
    return flattened


def count_header_rows(ws) -> int:
    """
    Count header rows between Source: row and first data row.
    
    Delegates to HeaderProcessor for core counting logic.
    
    Args:
        ws: openpyxl Worksheet object
        
    Returns:
        Number of header rows found
    """
    # Find the Source: row first
    source_row = None
    for row in range(1, 15):
        val = ws.cell(row, 1).value
        if val and 'source' in str(val).lower():
            source_row = row
            break
    
    if not source_row:
        return 0
    
    # Delegate to HeaderProcessor
    return HeaderProcessor.count_header_rows(ws, source_row)


def is_spanning_header_row(row_values: List) -> bool:
    """
    Detect if a row is a spanning header (L2) vs column headers (L3).
    
    Spanning headers have:
    - Period phrases like "Three Months Ended", "At September 30,"
    - Many empty cells (spans across columns)
    - No specific column data values
    
    Args:
        row_values: List of cell values for the row
    
    Returns:
        True if this looks like a spanning header that should be removed.
    """
    if not row_values:
        return False
    
    non_empty_count = sum(1 for v in row_values if v and str(v).strip())
    total_cols = len(row_values)
    
    # If less than 30% of cells are filled, it's likely a spanning header
    fill_ratio = non_empty_count / total_cols if total_cols > 0 else 0
    
    # Check for period phrases
    has_period_phrase = False
    period_patterns = [
        'three months ended', 'six months ended', 'nine months ended',
        'year ended', 'at ', 'as of ', 'for the period'
    ]
    
    for val in row_values:
        if val:
            val_lower = str(val).lower()
            for pattern in period_patterns:
                if pattern in val_lower:
                    has_period_phrase = True
                    break
    
    # Decision: It's a spanning header if:
    # 1. Has period phrases AND less than 50% fill ratio, OR
    # 2. Less than 30% fill ratio (mostly empty/spanning)
    if has_period_phrase and fill_ratio < 0.5:
        return True
    if fill_ratio < 0.3:
        return True
    
    return False


def are_duplicate_header_rows(row1: List, row2: List) -> bool:
    """
    Check if two header rows are duplicates or very similar.
    
    This handles cases where extraction created duplicate headers in rows 13 and 14.
    If they're the same, we should remove one row.
    
    Args:
        row1: First row values
        row2: Second row values
    
    Returns:
        True if rows are duplicates/similar enough to warrant flattening.
    """
    if not row1 or not row2:
        return False
    
    # Compare non-empty values
    r1_vals = [str(v).strip().lower() for v in row1 if v and str(v).strip()]
    r2_vals = [str(v).strip().lower() for v in row2 if v and str(v).strip()]
    
    if not r1_vals or not r2_vals:
        return False
    
    # Check if rows are identical
    if r1_vals == r2_vals:
        return True
    
    # Check if first row's content is subset of second row
    # (e.g., row 13 has just headers, row 14 has headers + first data)
    if len(r1_vals) <= len(r2_vals):
        overlap_count = sum(1 for v in r1_vals if v in r2_vals)
        if overlap_count >= len(r1_vals) * 0.7:
            return True
    
    return False
