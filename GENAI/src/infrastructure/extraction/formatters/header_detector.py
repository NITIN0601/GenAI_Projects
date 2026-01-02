"""
Header Detection for Excel Export.

Handles detection of:
- Multi-level column headers
- Row header levels (section vs line items)
- Unit indicators ($ in millions, etc.)
"""

import re
from typing import List, Dict, Any

from src.utils.financial_domain import UNIT_PATTERNS, is_unit_indicator


class HeaderDetector:
    """Detect and parse table header structures."""
    
    @classmethod
    def detect_column_header_levels(cls, content: str) -> Dict[str, Any]:
        """
        Detect multi-level column headers from markdown table content.
        
        Handles hierarchical headers like:
        | Row Labels | Three Months Ended Sept 30 | Nine Months Ended Sept 30 |
        |------------|------------|------------|------------|------------|
        | $ in millions | 2025 | 2024 | 2025 | 2024 |
        
        Returns:
            {
                'has_multi_level': bool,
                'level_1': List[str],  # Spanning headers (e.g., "Three Months Ended")
                'level_1_with_cols': List[str],  # With column positions (e.g., "Three Months Ended (cols 2-3)")
                'level_2': List[str]   # Sub-headers (e.g., "2025", "2024")
            }
        """
        lines = content.split('\n')
        
        # Find separator line index
        separator_idx = -1
        for i, line in enumerate(lines):
            if '|' in line and ('---' in line or '===' in line):
                separator_idx = i
                break
        
        if separator_idx == -1:
            return {'has_multi_level': False, 'level_1': [], 'level_1_with_cols': [], 'level_2': []}
        
        # Collect header lines BEFORE separator (Level 1 candidates)
        header_lines_before = []
        for i in range(separator_idx):
            if '|' in lines[i] and lines[i].strip():
                header_lines_before.append(lines[i])
        
        # === DYNAMIC MULTI-LEVEL HEADER DETECTION ===
        # Look for ALL header rows after separator until we hit a data row
        # A header row contains: date periods, repeated spanning text, or units
        # A data row contains: $ values, numbers, percentages in data cells
        
        def is_header_row(line: str) -> bool:
            """Dynamically detect if a row is a header row (not data)."""
            if not line or '|' not in line:
                return False
            
            # Parse cells (skip first column which is row labels)
            parts = [p.strip() for p in line.split('|') if p.strip()]
            if len(parts) < 2:
                return False
            
            data_cells = parts[1:]  # Skip row label column
            
            # Check for data indicators (means it's NOT a header row)
            # BUT exclude year patterns (2000-2039) from this check
            data_indicators = 0
            for cell in data_cells:
                if not cell:
                    continue
                # Skip if it's a year (4-digit year pattern)
                if re.match(r'^20[0-3]\d$', cell):
                    continue  # Years are headers, not data
                # Currency values, numbers with $ or parentheses
                if cell.startswith('$') or (cell.startswith('(') and cell.endswith(')')):
                    data_indicators += 1
                elif cell.replace(',', '').replace('.', '').replace('-', '').isdigit():
                    # Check if it's a large number (likely data, not a year)
                    clean_val = cell.replace(',', '').replace('.', '').replace('-', '')
                    if len(clean_val) > 4:  # More than 4 digits = data
                        data_indicators += 1
            
            # If most cells look like data, it's not a header row
            if data_indicators > len(data_cells) / 2:
                return False
            
            # Check for header patterns
            # Date periods
            if re.search(r'(months?|quarters?)\s+(ended|ending)', line, re.IGNORECASE):
                return True
            # Spanning headers (repeated values in adjacent cells)
            if len(set(c.lower() for c in data_cells if c)) < len([c for c in data_cells if c]):
                return True
            # Year patterns
            if re.search(r'\b20[0-3]\d\b', line):
                return True
            # Unit indicators
            if '$ in' in line.lower() or 'in millions' in line.lower():
                return True
            # "At" or "As of" date patterns
            if re.search(r'\b(at|as of)\s+\w+\s+\d+', line, re.IGNORECASE):
                return True
            
            return False
        
        # Collect all header rows after separator
        all_header_rows = []
        for i in range(separator_idx + 1, min(separator_idx + 5, len(lines))):  # Check up to 4 rows
            if i < len(lines) and '|' in lines[i]:
                if is_header_row(lines[i]):
                    all_header_rows.append(lines[i])
                else:
                    break  # Stop when we hit a data row
        
        if len(header_lines_before) == 0 and len(all_header_rows) == 0:
            return {'has_multi_level': False, 'level_0': [], 'level_1': [], 'level_1_with_cols': [], 'level_2': []}
        
        # Build header levels dynamically:
        # - Level 0: Top spanning headers BEFORE separator (e.g., "Average Monthly Balance")
        # - Level 1: Date period headers AFTER separator (e.g., "Three Months Ended June 30,")
        # - Level 2: Year/final sub-headers (e.g., "2024", "2023")
        
        level_0_headers = []  # NEW: Top-level spanning header
        level_0_with_cols = []
        level_1_headers = []  # Date periods
        level_2_headers = []  # Years
        
        # Parse header rows before separator (Level 0 - top spanning)
        if header_lines_before:
            level_0_with_positions = cls._parse_header_with_columns(header_lines_before[0])
            level_0_headers = cls._dedupe_spanning_headers([h['text'] for h in level_0_with_positions])
            
            # Format with column positions
            for h in level_0_with_positions:
                if h['text']:
                    if h['start_col'] == h['end_col']:
                        col_info = f"(col {h['start_col']})"
                    else:
                        col_info = f"(cols {h['start_col']}-{h['end_col']})"
                    level_0_with_cols.append(f"{h['text']} {col_info}")
            level_0_with_cols = cls._dedupe_spanning_headers(level_0_with_cols)
        
        # Parse header rows after separator - distribute to Level 1 and Level 2
        for idx, header_row in enumerate(all_header_rows):
            row_headers = cls._parse_header_line_skip_col1(header_row)
            
            # Check if this row contains years (likely Level 2)
            has_years = bool(re.search(r'\b20[0-3]\d\b', header_row))
            
            if has_years:
                # Row with years goes to Level 2
                level_2_headers.extend(row_headers)
            else:
                # Date period rows go to Level 1
                level_1_headers.extend(row_headers)
        
        # Deduplicate
        level_1_headers = cls._dedupe_spanning_headers(level_1_headers)
        level_2_headers = cls._dedupe_spanning_headers(level_2_headers)
        
        # === SMART LEVEL ASSIGNMENT ===
        # If we only have 2 levels total (Level 0 + Level 2, or just Level 0),
        # shift everything down so Level 0 is empty and main headers go to Level 1
        total_levels = sum([
            len(level_0_headers) > 0,
            len(level_1_headers) > 0,
            len(level_2_headers) > 0
        ])
        
        if total_levels <= 2 and len(level_0_headers) > 0 and len(level_1_headers) == 0:
            # Only 2 levels: shift Level 0 → Level 1, leave Level 0 empty
            level_1_headers = level_0_headers
            level_0_headers = []
            level_0_with_cols = []
        
        # Determine if multi-level (has at least 2 levels populated)
        has_multi_level = sum([
            len(level_0_headers) > 0,
            len(level_1_headers) > 0,
            len(level_2_headers) > 0
        ]) >= 2
        
        return {
            'has_multi_level': has_multi_level,
            'level_0': level_0_headers,           # Top spanning (e.g., "Average Monthly Balance")
            'level_0_with_cols': level_0_with_cols,
            'level_1': level_1_headers,           # Date periods (e.g., "Three Months Ended")
            'level_1_with_cols': [],              # TODO: add if needed
            'level_2': level_2_headers            # Years (e.g., "2024", "2023")
        }
    
    @classmethod
    def _is_subheader_row(cls, line: str) -> bool:
        """Check if a row looks like a sub-header row (years, units, percentages)."""
        line_lower = line.lower()
        # Check for year patterns
        if re.search(r'\b20[2-9]\d\b', line):
            return True
        # Check for unit indicators
        if '$ in' in line_lower or 'in millions' in line_lower:
            return True
        # Check for percentage sign
        if '%' in line and 'change' not in line_lower:
            return True
        return False
    
    @classmethod
    def _parse_header_with_columns(cls, line: str) -> List[Dict[str, Any]]:
        """
        Parse header line and track which columns each header spans.
        
        For a line like:
        |          | Three Months Ended | Three Months Ended | Nine Months Ended | Nine Months Ended |
        
        Returns:
        [
            {'text': 'Three Months Ended', 'start_col': 2, 'end_col': 3},
            {'text': 'Nine Months Ended', 'start_col': 4, 'end_col': 5}
        ]
        """
        parts = line.split('|')
        
        # Remove empty first/last parts
        if parts and not parts[0].strip():
            parts = parts[1:]
        if parts and not parts[-1].strip():
            parts = parts[:-1]
        
        if len(parts) <= 1:
            return []
        
        # Skip column 1 (row labels) - start from column 2
        result = []
        current_header = None
        start_col = 2  # Column 2 is first data column
        
        for i, part in enumerate(parts[1:], start=2):  # Skip first column
            text = part.strip()
            
            if not text:
                continue
            
            if current_header is None:
                # Start a new header
                current_header = text
                start_col = i
            elif text.lower() == current_header.lower():
                # Same header continues (spanning)
                pass
            else:
                # Different header - save the current one
                result.append({
                    'text': current_header,
                    'start_col': start_col,
                    'end_col': i - 1
                })
                # Start new header
                current_header = text
                start_col = i
        
        # Don't forget the last header
        if current_header:
            result.append({
                'text': current_header,
                'start_col': start_col,
                'end_col': len(parts)  # Last column
            })
        
        return result
    
    @classmethod
    def _parse_header_line_skip_col1(cls, line: str) -> List[str]:
        """Parse a markdown header line, SKIPPING column 1 (row labels)."""
        parts = line.split('|')
        # Remove empty first/last parts
        if parts and not parts[0].strip():
            parts = parts[1:]
        if parts and not parts[-1].strip():
            parts = parts[:-1]
        
        # Skip column 1 (which is typically row labels like "$ in millions")
        if len(parts) > 1:
            parts = parts[1:]  # Skip first column
        
        return [p.strip() for p in parts if p.strip()]
    
    @classmethod
    def _dedupe_spanning_headers(cls, headers: List[str]) -> List[str]:
        """
        Deduplicate spanning headers that Docling repeats.
        
        Example: ["Three Months Ended", "Three Months Ended", "Nine Months Ended", "Nine Months Ended"]
        Returns: ["Three Months Ended", "Nine Months Ended"]
        
        Also handles headers with Level N suffixes:
        ["At Sept 30, 2025 Level 1", "At Sept 30, 2025 Level 2"]
        Returns: ["At Sept 30, 2025"]
        """
        if not headers:
            return []
        
        seen_normalized = set()
        result = []
        for h in headers:
            if not h or not h.strip():
                continue
            
            # Use centralized normalization
            h_normalized = cls._normalize_for_dedup(h)
            
            if h_normalized and h_normalized not in seen_normalized:
                seen_normalized.add(h_normalized)
                # Clean the header before storing
                clean_h = re.sub(r'\s*Level\s*\d+\s*$', '', h.strip(), flags=re.IGNORECASE)
                result.append(clean_h.strip())
        
        return result
    
    @staticmethod
    def _parse_header_line(line: str) -> List[str]:
        """Parse a markdown header line into cells."""
        parts = line.split('|')
        if parts and not parts[0].strip():
            parts = parts[1:]
        if parts and not parts[-1].strip():
            parts = parts[:-1]
        return [p.strip() for p in parts if p.strip()]
    
    @classmethod
    def _normalize_for_dedup(cls, header: str) -> str:
        """
        Normalize a header string for deduplication comparison.
        
        Strips common suffixes that make headers appear different but are 
        semantically the same:
        - "Level 1", "Level 2", "Level 3" suffixes
        - "(1)", "(2)", "(3)" suffixes
        - "Fair Value", "Carrying Value" suffixes (for fair value tables)
        - Leading/trailing whitespace and extra spaces
        
        Args:
            header: Original header string
            
        Returns:
            Normalized header for comparison
        """
        if not header:
            return ''
        
        h = str(header).strip()
        
        # Remove Level N suffixes (common in multi-level tables)
        h = re.sub(r'\s*Level\s*\d+\s*$', '', h, flags=re.IGNORECASE)
        
        # Remove parenthesized numbers at end: (1), (2), etc.
        h = re.sub(r'\s*\(\d+\)\s*$', '', h)
        
        # Remove trailing "1" or "2" that might be footnote refs
        h = re.sub(r'\s+\d\s*$', '', h)
        
        # Remove common suffixes that differentiate but don't add semantic value
        h = re.sub(r'\s*(Fair Value|Carrying Value|Amortized Cost)\s*$', '', h, flags=re.IGNORECASE)
        
        # Normalize whitespace
        h = re.sub(r'\s+', ' ', h).strip()
        
        return h.lower()
    
    @classmethod
    def dedupe_preserve_order(cls, items: List[str]) -> List[str]:
        """
        Deduplicate a list while preserving order.
        
        Uses intelligent normalization to detect headers that differ only by
        suffixes like "Level 1", "Level 2" and treats them as duplicates.
        Keeps the first occurrence (typically the simplest form).
        """
        seen_normalized = set()
        result = []
        
        for item in items:
            if not item or str(item).lower() in ['nan', 'none', 'unnamed', '']:
                continue
            
            # Normalize for comparison
            normalized = cls._normalize_for_dedup(item)
            
            if normalized and normalized not in seen_normalized:
                seen_normalized.add(normalized)
                # Store the original item (or a cleaned version without Level suffix)
                clean_item = re.sub(r'\s*Level\s*\d+\s*$', '', str(item).strip(), flags=re.IGNORECASE)
                result.append(clean_item.strip())
        
        return result
    
    @classmethod
    def is_unit_indicator(cls, text: str) -> bool:
        """
        Check if text is a unit indicator.
        
        Examples: "$ in millions", "(in thousands)", "amounts in billions"
        
        Delegates to shared is_unit_indicator utility.
        """
        return is_unit_indicator(text)
    
    @classmethod
    def extract_years_from_headers(cls, headers: List[str]) -> List[str]:
        """
        Extract year values from header strings.
        
        Args:
            headers: List of header strings
            
        Returns:
            Sorted list of years (most recent first)
        """
        years = set()
        for header in headers:
            year_match = re.search(r'(20\d{2})', str(header))
            if year_match:
                years.add(year_match.group(1))
        return sorted(years, reverse=True)


# Convenience function for backward compatibility
def detect_column_headers(content: str) -> Dict[str, Any]:
    """Detect column header levels from table content."""
    return HeaderDetector.detect_column_header_levels(content)
