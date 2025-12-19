"""
Header Detection for Excel Export.

Handles detection of:
- Multi-level column headers
- Row header levels (section vs line items)
- Unit indicators ($ in millions, etc.)
"""

import re
from typing import List, Dict, Any


class HeaderDetector:
    """Detect and parse table header structures."""
    
    # Unit indicator patterns to filter from Product/Entity
    UNIT_PATTERNS = [
        '$ in million', '$ in billion', '$ in thousand',
        'in millions', 'in billions', 'in thousands',
        'dollars in millions', 'dollars in billions',
        '(in millions)', '(in billions)', '(in thousands)',
        'amounts in millions', 'amounts in billions',
    ]
    
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
            return {'has_multi_level': False, 'level_1': [], 'level_2': []}
        
        # Collect header lines BEFORE separator (Level 1 candidates)
        header_lines_before = []
        for i in range(separator_idx):
            if '|' in lines[i] and lines[i].strip():
                header_lines_before.append(lines[i])
        
        # Check first data row AFTER separator for Level 2 (years, units)
        level_2_row = None
        first_data_row_idx = separator_idx + 1
        if first_data_row_idx < len(lines) and '|' in lines[first_data_row_idx]:
            potential_level_2 = lines[first_data_row_idx]
            # Check if this row contains years (2020-2029) or unit indicators
            if re.search(r'\b20[2-9]\d\b', potential_level_2) or cls._is_subheader_row(potential_level_2):
                level_2_row = potential_level_2
        
        if len(header_lines_before) == 0:
            # No headers before separator - check if level_2_row found
            if level_2_row:
                level_2_headers = cls._parse_header_line_skip_col1(level_2_row)
                return {'has_multi_level': False, 'level_1': level_2_headers, 'level_2': []}
            return {'has_multi_level': False, 'level_1': [], 'level_2': []}
        
        # Parse header row before separator (Level 1)
        # Skip column 1 which is typically row labels
        level_1_headers = cls._parse_header_line_skip_col1(header_lines_before[0])
        
        # Dedupe repeated spanning headers (Docling repeats merged cells)
        level_1_unique = cls._dedupe_spanning_headers(level_1_headers)
        
        # Parse Level 2 if found
        level_2_headers = []
        if level_2_row:
            level_2_headers = cls._parse_header_line_skip_col1(level_2_row)
        
        # Determine if multi-level
        has_multi_level = len(level_1_unique) > 0 and len(level_2_headers) > 0
        
        if has_multi_level:
            return {
                'has_multi_level': True,
                'level_1': level_1_unique,    # Spanning headers (deduplicated)
                'level_2': level_2_headers    # Sub-headers (years)
            }
        else:
            # Single level - combine
            all_headers = level_1_unique + level_2_headers
            return {
                'has_multi_level': False,
                'level_1': all_headers,
                'level_2': []
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
        """
        if not headers:
            return []
        
        seen = set()
        result = []
        for h in headers:
            h_normalized = h.strip().lower()
            if h_normalized and h_normalized not in seen:
                seen.add(h_normalized)
                result.append(h.strip())
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
    def dedupe_preserve_order(cls, items: List[str]) -> List[str]:
        """Deduplicate a list while preserving order."""
        seen = set()
        result = []
        for item in items:
            if item and item not in seen and str(item).lower() not in ['nan', 'none', 'unnamed', '']:
                seen.add(item)
                result.append(item)
        return result
    
    @classmethod
    def is_unit_indicator(cls, text: str) -> bool:
        """
        Check if text is a unit indicator.
        
        Examples: "$ in millions", "(in thousands)", "amounts in billions"
        """
        if not text:
            return False
            
        text_lower = text.lower().strip()
        
        for pattern in cls.UNIT_PATTERNS:
            if pattern in text_lower:
                return True
        
        # Also exclude if it starts with $ and contains 'in'
        if text_lower.startswith('$') and ' in ' in text_lower:
            return True
        
        return False
    
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
