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
        
        Returns:
            {
                'has_multi_level': bool,
                'level_1': List[str],  # Main/spanning headers
                'level_2': List[str]   # Sub-headers (typically with dates/years)
            }
        """
        lines = content.split('\n')
        header_lines = []
        
        # Find header lines (before separator)
        for i, line in enumerate(lines):
            if '|' in line and ('---' in line or '===' in line):
                break
            if '|' in line and line.strip():
                header_lines.append(line)
        
        if len(header_lines) == 0:
            return {'has_multi_level': False, 'level_1': [], 'level_2': []}
        
        if len(header_lines) == 1:
            # Single header row
            headers = cls._parse_header_line(header_lines[0])
            return {'has_multi_level': False, 'level_1': headers, 'level_2': []}
        
        # Multi-line headers (2+ rows)
        first_row = cls._parse_header_line(header_lines[0])
        second_row = cls._parse_header_line(header_lines[1])
        
        # Check if first row has fewer non-empty cells (spanning header pattern)
        # Or first row has more generic terms (like "Three Months Ended")
        first_row_filled = len([c for c in first_row if c])
        second_row_filled = len([c for c in second_row if c])
        
        has_multi_level = (
            first_row_filled < second_row_filled or 
            len(header_lines) > 1 and any('ended' in h.lower() or 'month' in h.lower() for h in first_row)
        )
        
        if has_multi_level:
            return {
                'has_multi_level': True,
                'level_1': first_row,  # Spanning headers
                'level_2': second_row  # Sub-headers (often with dates)
            }
        else:
            # Not multi-level, combine all headers
            all_headers = first_row + second_row
            return {
                'has_multi_level': False,
                'level_1': all_headers,
                'level_2': []
            }
    
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
