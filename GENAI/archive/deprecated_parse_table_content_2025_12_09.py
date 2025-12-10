"""
ARCHIVED CODE - December 9, 2025

This file contains the original duplicate implementations of _parse_table_content()
that were replaced with calls to the shared utility in src/utils/table_utils.py.

Archived from:
- src/infrastructure/extraction/formatters/excel_exporter.py
- src/infrastructure/extraction/consolidation/consolidator.py

Reason: Code deduplication - consolidated into parse_markdown_table() in table_utils.py
"""

import pandas as pd

# ============================================================================
# From: excel_exporter.py (lines 388-428)
# Replaced with: parse_markdown_table(content, handle_colon_separator=False)
# ============================================================================

def _parse_table_content_excel_exporter(self, content: str) -> pd.DataFrame:
    """Parse markdown/text table content to DataFrame."""
    try:
        from src.utils.extraction_utils import CurrencyValueCleaner
        
        # Clean currency values
        cleaned = CurrencyValueCleaner.clean_table_rows(content)
        lines = [l.strip() for l in cleaned.split('\n') if l.strip()]
        
        # Remove separator lines
        lines = [l for l in lines if not all(c in '|-: ' for c in l)]
        
        if not lines:
            return pd.DataFrame()
        
        rows = []
        for line in lines:
            if '|' in line:
                cells = [c.strip() for c in line.split('|')]
                cells = [c for c in cells if c]
                cells = CurrencyValueCleaner.clean_currency_cells(cells)
                if cells:
                    rows.append(cells)
        
        if not rows or len(rows) < 2:
            return pd.DataFrame()
        
        # First row is header
        header = rows[0]
        data = rows[1:]
        
        # Pad rows
        max_cols = max(len(header), max(len(r) for r in data) if data else 0)
        header = header + [''] * (max_cols - len(header))
        data = [r + [''] * (max_cols - len(r)) for r in data]
        
        return pd.DataFrame(data, columns=header)
        
    except Exception as e:
        # logger.error(f"Error parsing table content: {e}")
        return pd.DataFrame()


# ============================================================================
# From: consolidator.py (lines 385-430)
# Replaced with: parse_markdown_table(content, handle_colon_separator=True)
# ============================================================================

def _parse_table_content_consolidator(self, content: str) -> pd.DataFrame:
    """Parse markdown/text table to DataFrame with currency cleaning."""
    try:
        from src.utils.extraction_utils import CurrencyValueCleaner
        
        # Clean currency values first
        cleaned_content = CurrencyValueCleaner.clean_table_rows(content)
        
        lines = [l.strip() for l in cleaned_content.split('\n') if l.strip()]
        
        # Remove separator lines
        lines = [l for l in lines if not all(c in '|-: ' for c in l)]
        
        if not lines:
            return pd.DataFrame()
        
        rows = []
        for line in lines:
            if '|' in line:
                cells = [c.strip() for c in line.split('|')]
                cells = [c for c in cells if c]
                cells = CurrencyValueCleaner.clean_currency_cells(cells)
                if cells:
                    rows.append(cells)
            elif ':' in line:
                # This was the ONLY difference from excel_exporter version
                parts = line.split(':', 1)
                if len(parts) == 2:
                    rows.append([parts[0].strip(), parts[1].strip()])
        
        if not rows or len(rows) < 2:
            return pd.DataFrame()
        
        # First row is header
        header = rows[0]
        data = rows[1:]
        
        # Pad rows to match header length
        max_cols = max(len(header), max(len(r) for r in data) if data else 0)
        header = header + [''] * (max_cols - len(header))
        data = [r + [''] * (max_cols - len(r)) for r in data]
        
        return pd.DataFrame(data, columns=header)
        
    except Exception as e:
        # logger.error(f"Error parsing table content: {e}")
        return pd.DataFrame()
