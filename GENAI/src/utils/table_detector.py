"""
Table Detector - Reusable table boundary detection.

Extracted from process.py for modularity and reusability.

Used by: ProcessStep, and any module needing table detection in worksheets.
"""

from typing import List, Dict, Any
from src.utils import get_logger

logger = get_logger(__name__)


class TableDetector:
    """
    Detect table boundaries within Excel worksheets.
    
    Tables are identified by:
    - "Source:" or "Source(s):" marker rows
    - "Table Title:" rows  
    - Empty rows between tables
    
    Design: Stateless methods for horizontal scaling.
    """
    
    @classmethod
    def find_table_boundaries(cls, ws) -> List[Dict[str, Any]]:
        """
        Find all tables in a worksheet by identifying boundaries.
        
        Args:
            ws: openpyxl worksheet object
            
        Returns:
            List of dicts with 'start_row', 'end_row', 'header_row', 'source_row'
        """
        tables = []
        current_table_start = None
        
        for row in range(1, ws.max_row + 1):
            col_a = ws.cell(row, 1).value
            
            if col_a:
                col_a_str = str(col_a).strip()
                col_a_lower = col_a_str.lower()
                
                # Source row marks table boundary
                is_source_row = (
                    col_a_lower.startswith('source(s):') or
                    col_a_lower.startswith('source:')
                )
                
                if is_source_row:
                    if current_table_start is not None:
                        tables.append({
                            'start_row': current_table_start,
                            'end_row': row - 1,
                            'source_row': current_table_start
                        })
                    current_table_start = row
        
        # Last table
        if current_table_start is not None:
            tables.append({
                'start_row': current_table_start, 
                'end_row': ws.max_row,
                'source_row': current_table_start
            })
        
        # Find header rows for each table
        for table in tables:
            source_row = table['source_row']
            header_row = None
            
            for row in range(source_row + 1, min(table['end_row'] + 1, source_row + 10)):
                col_b = ws.cell(row, 2).value
                if col_b and str(col_b).strip():
                    header_row = row
                    break
            
            table['header_row'] = header_row if header_row else source_row + 2
        
        return tables
    
    @classmethod
    def count_tables(cls, ws) -> int:
        """Count tables in worksheet."""
        return len(cls.find_table_boundaries(ws))


__all__ = ['TableDetector']
