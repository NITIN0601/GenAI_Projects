"""
Metadata enrichment for extracted tables.

Handles detection of:
- Financial units (millions, billions, etc.)
- Currency (USD, EUR, etc.)
- Statement types (Balance Sheet, Income Statement, etc.)
- Table structure classification
"""

import re
from typing import Dict, Any, Optional, List

class MetadataEnricher:
    """Enriches table metadata with financial context."""
    
    def __init__(self):
        self.statement_keywords = {
            'balance_sheet': ['balance sheet', 'financial position', 'assets', 'liabilities'],
            'income_statement': ['income statement', 'operations', 'earnings', 'profit', 'loss'],
            'cash_flow': ['cash flow', 'cash flows'],
            'equity': ['equity', 'stockholders', 'shareholders'],
            'footnotes': ['note', 'footnote']
        }
        
        self.unit_patterns = {
            'millions': [r'in millions', r'\(in millions\)', r'\$ millions'],
            'thousands': [r'in thousands', r'\(in thousands\)', r'\$ thousands'],
            'billions': [r'in billions', r'\(in billions\)', r'\$ billions']
        }

    def enrich_table_metadata(self, content: str, table_title: str, existing_metadata: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Enrich metadata based on table content and title.
        
        Args:
            content: Table text content
            table_title: Title of the table
            existing_metadata: Existing metadata to update
            
        Returns:
            Updated metadata dictionary
        """
        metadata = existing_metadata.copy() if existing_metadata else {}
        
        # Detect units
        units = self._detect_units(content)
        if units:
            metadata['units'] = units
            
        # Detect currency
        currency, has_currency = self._detect_currency(content)
        metadata['currency'] = currency
        metadata['has_currency'] = has_currency
        
        # Detect statement type
        statement_type = self._detect_statement_type(table_title)
        if statement_type:
            metadata['statement_type'] = statement_type
            
        # Detect structure info (simple vs complex)
        # This is a heuristic based on content analysis
        metadata.update(self._analyze_structure(content))
        
        return metadata

    def _detect_units(self, content: str) -> Optional[str]:
        """Detect financial units from content."""
        content_lower = content.lower()
        for unit, patterns in self.unit_patterns.items():
            for pattern in patterns:
                if re.search(pattern, content_lower):
                    return unit
        return None

    def _detect_currency(self, content: str) -> tuple[str, bool]:
        """Detect currency and if it's present."""
        content_lower = content.lower()
        if '$' in content or 'usd' in content_lower:
            return "USD", True
        if '€' in content or 'eur' in content_lower:
            return "EUR", True
        if '£' in content or 'gbp' in content_lower:
            return "GBP", True
            
        return "USD", False  # Default to USD if uncertain but likely financial

    def _detect_statement_type(self, title: str) -> Optional[str]:
        """Detect financial statement type from title."""
        title_lower = title.lower()
        for st_type, keywords in self.statement_keywords.items():
            if any(k in title_lower for k in keywords):
                return st_type
        return None

    def _analyze_structure(self, content: str) -> Dict[str, Any]:
        """Analyze table structure (columns, rows, complexity)."""
        lines = content.split('\n')
        rows = [line for line in lines if line.strip() and '|' in line]
        
        if not rows:
            return {'row_count': 0, 'column_count': 0, 'table_structure': 'unknown'}
            
        # Estimate column count from the first data row (or header)
        # Using max columns found in first few rows to be safe
        max_cols = 0
        for row in rows[:5]:
            cols = len([c for c in row.split('|') if c.strip()])
            max_cols = max(max_cols, cols)
            
        row_count = len([r for r in rows if '---' not in r])
        
        # Heuristic for complexity
        structure = "simple"
        if max_cols > 3:
            structure = "multi_column"
        
        # Check for multi-level headers (colspan indicators or empty cells in header area)
        # This is a simplified check
        has_multi_level = False
        if len(rows) > 2:
             # If first row has fewer filled cells than max_cols, it might be a spanning header
             first_row_cols = len([c for c in rows[0].split('|') if c.strip()])
             if first_row_cols < max_cols and first_row_cols > 0:
                 has_multi_level = True
                 structure = "multi_header"

        return {
            'row_count': row_count,
            'column_count': max_cols,
            'table_structure': structure,
            'has_multi_level_headers': has_multi_level
        }

# Singleton instance
_enricher_instance = None

def get_metadata_enricher() -> MetadataEnricher:
    """Get singleton MetadataEnricher instance."""
    global _enricher_instance
    if _enricher_instance is None:
        _enricher_instance = MetadataEnricher()
    return _enricher_instance
