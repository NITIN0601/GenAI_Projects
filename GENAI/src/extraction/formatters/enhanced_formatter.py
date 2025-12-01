"""
Enhanced table structure formatter with advanced features.

Features:
- Multi-level header detection (spanning headers)
- Currency formatting preservation
- Subsection detection
- Hierarchical row structure
"""

from typing import Dict, List, Any, Tuple, Optional
import re


class EnhancedTableFormatter:
    """Enhanced table formatter with multi-level header support."""
    
    @staticmethod
    def detect_multi_level_headers(lines: List[str]) -> Dict[str, Any]:
        """
        Detect multi-level headers in table.
        
        Returns:
            {
                'has_multi_level': bool,
                'main_header': str,  # Spanning header
                'sub_headers': List[str],  # Column headers
                'header_rows': List[str]
            }
        """
        header_rows = []
        
        # Find header rows (before separator line)
        for i, line in enumerate(lines):
            if line.strip().startswith('|---') or line.strip().startswith('---'):
                break
            if '|' in line:
                header_rows.append(line)
        
        if len(header_rows) == 0:
            return {
                'has_multi_level': False,
                'main_header': None,
                'sub_headers': [],
                'header_rows': []
            }
        
        # Check if first row has fewer populated cells (spanning header)
        first_row_cells = [c.strip() for c in header_rows[0].split('|') if c.strip()]
        
        if len(header_rows) > 1:
            second_row_cells = [c.strip() for c in header_rows[1].split('|') if c.strip()]
            
            # Multi-level if first row has fewer cells or different structure
            has_multi_level = len(first_row_cells) < len(second_row_cells)
            
            return {
                'has_multi_level': has_multi_level,
                'main_header': ' | '.join(first_row_cells) if has_multi_level else None,
                'sub_headers': second_row_cells if has_multi_level else first_row_cells,
                'header_rows': header_rows
            }
        
        return {
            'has_multi_level': False,
            'main_header': None,
            'sub_headers': first_row_cells,
            'header_rows': header_rows
        }
    
    @staticmethod
    def detect_subsections(lines: List[str]) -> List[Dict[str, Any]]:
        """
        Detect subsections within table (rows with single populated cell).
        
        Returns:
            List of {
                'line_no': int,
                'text': str,
                'is_subsection': bool
            }
        """
        subsections = []
        
        for i, line in enumerate(lines):
            if '|' not in line or line.strip().startswith('|---'):
                continue
            
            cells = [c.strip() for c in line.split('|')]
            non_empty = [c for c in cells if c]
            
            # Subsection if only one non-empty cell
            if len(non_empty) == 1:
                subsections.append({
                    'line_no': i,
                    'text': non_empty[0],
                    'is_subsection': True
                })
        
        return subsections
    
    @staticmethod
    def fix_currency_formatting(content: str) -> str:
        """
        Ensure currency symbols stay with values in same cell.
        
        Fixes patterns like:
        - "$ | 15,136" → "$ 15,136"
        - "2024 $ | 15,136" → "2024 | $ 15,136"
        """
        lines = content.split('\n')
        fixed_lines = []
        
        for line in lines:
            if '|' not in line:
                fixed_lines.append(line)
                continue
            
            # Split into cells
            cells = line.split('|')
            fixed_cells = []
            
            for i, cell in enumerate(cells):
                cell = cell.strip()
                
                # Check if next cell starts with a number and current ends with $
                if i < len(cells) - 1:
                    next_cell = cells[i + 1].strip()
                    
                    # Pattern: "$ | 15,136" or "2024 $ | 15,136"
                    if cell.endswith('$') and next_cell and next_cell[0].isdigit():
                        # Move $ to next cell
                        cell = cell[:-1].strip()
                        next_cell = '$ ' + next_cell
                        cells[i + 1] = next_cell
                
                fixed_cells.append(cell)
            
            # Reconstruct line
            fixed_line = '| ' + ' | '.join(fixed_cells) + ' |'
            fixed_lines.append(fixed_line)
        
        return '\n'.join(fixed_lines)
    
    @staticmethod
    def format_enhanced_table(table_dict: Dict[str, Any]) -> str:
        """
        Format table with enhanced structure detection.
        
        Args:
            table_dict: Table dictionary from extraction
            
        Returns:
            Formatted string with enhanced structure
        """
        content = table_dict.get('content', '')
        metadata = table_dict.get('metadata', {})
        
        # Fix currency formatting first
        content = EnhancedTableFormatter.fix_currency_formatting(content)
        
        lines = content.split('\n')
        
        # Detect multi-level headers
        header_info = EnhancedTableFormatter.detect_multi_level_headers(lines)
        
        # Detect subsections
        subsections = EnhancedTableFormatter.detect_subsections(lines)
        
        # Build output
        output = []
        output.append("=" * 80)
        output.append(f"Table Title: {metadata.get('table_title', 'N/A')}")
        output.append("=" * 80)
        
        # Header information
        if header_info['has_multi_level']:
            output.append(f"\n📋 Multi-Level Headers:")
            output.append(f"   Main Header: {header_info['main_header']}")
            output.append(f"   Sub Headers: {' | '.join(header_info['sub_headers'])}")
        else:
            output.append(f"\n📋 Column Headers: {' | '.join(header_info['sub_headers'])}")
        
        # Subsections
        if subsections:
            output.append(f"\n📑 Subsections Found: {len(subsections)}")
            for subsection in subsections[:3]:
                output.append(f"   - {subsection['text']}")
            if len(subsections) > 3:
                output.append(f"   ... and {len(subsections) - 3} more")
        
        # Table dimensions
        data_rows = [l for l in lines if '|' in l and not l.strip().startswith('|---')]
        output.append(f"\n📏 Table Size:")
        output.append(f"   Columns: {len(header_info['sub_headers'])}")
        output.append(f"   Rows: {len(data_rows) - len(header_info['header_rows'])}")
        
        # Currency analysis
        currency_count = content.count('$')
        if currency_count > 0:
            output.append(f"\n💰 Currency Values: {currency_count} cells with $ symbol")
        
        # Table content
        output.append(f"\n📄 Table:")
        output.append("-" * 80)
        for line in lines[:25]:
            output.append(line)
        if len(lines) > 25:
            output.append(f"... ({len(lines) - 25} more lines)")
        output.append("-" * 80)
        
        return '\n'.join(output)
    
    @staticmethod
    def format_all_tables_enhanced(extraction_result) -> str:
        """
        Format all tables with enhanced detection.
        
        Args:
            extraction_result: ExtractionResult object
            
        Returns:
            Formatted string
        """
        output = []
        output.append("=" * 80)
        output.append("ENHANCED TABLE STRUCTURE REPORT")
        output.append("=" * 80)
        output.append(f"\nFile: {extraction_result.pdf_path}")
        output.append(f"Backend: {extraction_result.backend.value}")
        output.append(f"Total Tables: {len(extraction_result.tables)}\n")
        
        for i, table in enumerate(extraction_result.tables, 1):
            output.append(f"\n[TABLE {i}]")
            formatted = EnhancedTableFormatter.format_enhanced_table(table)
            output.append(formatted)
            output.append("\n")
        
        return '\n'.join(output)


# Convenience functions
def format_enhanced_table(table_dict: Dict[str, Any]) -> str:
    """Format a single table with enhanced features."""
    return EnhancedTableFormatter.format_enhanced_table(table_dict)


def format_all_tables_enhanced(extraction_result) -> str:
    """Format all tables with enhanced features."""
    return EnhancedTableFormatter.format_all_tables_enhanced(extraction_result)
