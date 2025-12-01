"""
Enhanced table structure formatter for extraction results.

Provides structured output format for tables with:
- Table title
- Column headers
- Row headers (with hierarchy detection)
- Table dimensions
- Formatted table content
"""

from typing import Dict, List, Any, Tuple, Optional


class TableStructureFormatter:
    """Format extracted tables with detailed structure information."""
    
    @staticmethod
    def parse_markdown_table(markdown_content: str) -> Dict[str, Any]:
        """
        Parse markdown table into structured format.
        
        Args:
            markdown_content: Markdown table string
            
        Returns:
            Dictionary with table structure information
        """
        lines = [line.strip() for line in markdown_content.split('\n') if line.strip()]
        
        # Find header and data rows
        header_row = None
        data_rows = []
        
        for line in lines:
            if '|' not in line:
                continue
            if line.startswith('|---') or line.startswith('---'):
                continue  # Skip separator
            
            if header_row is None:
                header_row = line
            else:
                data_rows.append(line)
        
        # Parse columns
        columns = []
        if header_row:
            columns = [col.strip() for col in header_row.split('|') if col.strip()]
        
        # Parse data
        parsed_rows = []
        for row in data_rows:
            cells = [cell.strip() for cell in row.split('|') if cell.strip() or cell == '']
            # Handle empty cells (spanning)
            cells = [cell if cell else '' for cell in cells]
            parsed_rows.append(cells)
        
        return {
            'columns': columns,
            'column_count': len(columns),
            'rows': parsed_rows,
            'row_count': len(parsed_rows)
        }
    
    @staticmethod
    def detect_row_hierarchy(rows: List[List[str]]) -> List[Dict[str, Any]]:
        """
        Detect hierarchical structure in row headers.
        
        Args:
            rows: List of row data (list of cells)
            
        Returns:
            List of row information with hierarchy level
        """
        hierarchical_rows = []
        current_category = None
        current_subcategory = None
        
        for row in rows:
            if not row:
                continue
            
            # First column is typically the main category
            first_col = row[0] if len(row) > 0 else ''
            second_col = row[1] if len(row) > 1 else ''
            
            # Detect hierarchy level
            if first_col and first_col != current_category:
                # New main category
                current_category = first_col
                current_subcategory = second_col if second_col else None
                level = 0
            elif not first_col and second_col:
                # Subcategory (first column empty)
                current_subcategory = second_col
                level = 1
            elif not first_col and not second_col:
                # Detail row (both empty)
                level = 2
            else:
                level = 0
            
            hierarchical_rows.append({
                'cells': row,
                'level': level,
                'category': current_category,
                'subcategory': current_subcategory
            })
        
        return hierarchical_rows
    
    @staticmethod
    def format_table_structure(
        table_dict: Dict[str, Any],
        include_content: bool = True
    ) -> str:
        """
        Format table with structure information.
        
        Args:
            table_dict: Table dictionary from extraction
            include_content: Whether to include full table content
            
        Returns:
            Formatted string with table structure
        """
        content = table_dict.get('content', '')
        metadata = table_dict.get('metadata', {})
        
        # Parse table
        parsed = TableStructureFormatter.parse_markdown_table(content)
        
        # Build output
        output = []
        output.append("=" * 80)
        output.append(f"Table Title: {metadata.get('table_title', 'N/A')}")
        output.append("=" * 80)
        
        # Column headers
        output.append(f"\nColumn Headers: {' | '.join(parsed['columns'])}")
        
        # Detect row hierarchy
        hierarchical_rows = TableStructureFormatter.detect_row_hierarchy(parsed['rows'])
        
        # Row headers (first column values)
        row_headers = [row['cells'][0] if row['cells'] else '' for row in hierarchical_rows]
        unique_row_headers = [h for h in row_headers if h]  # Non-empty
        output.append(f"Row Headers: {', '.join(unique_row_headers[:5])}")
        if len(unique_row_headers) > 5:
            output.append(f"             ... and {len(unique_row_headers) - 5} more")
        
        # Table size
        output.append(f"\nTable Size:")
        output.append(f"  Columns: {parsed['column_count']}")
        output.append(f"  Rows: {parsed['row_count']}")
        
        # Hierarchy detection
        has_hierarchy = any(row['level'] > 0 for row in hierarchical_rows)
        output.append(f"  Hierarchical Structure: {'Yes' if has_hierarchy else 'No'}")
        
        # Table content
        if include_content:
            output.append(f"\nTable:")
            output.append("-" * 80)
            content_lines = content.split('\n')
            for line in content_lines[:20]:  # First 20 lines
                output.append(line)
            if len(content_lines) > 20:
                remaining_lines = len(content_lines) - 20
                output.append(f"... ({remaining_lines} more lines)")
            output.append("-" * 80)
        
        return '\n'.join(output)
    
    @staticmethod
    def format_all_tables(
        extraction_result,
        include_content: bool = False
    ) -> str:
        """
        Format all tables from extraction result.
        
        Args:
            extraction_result: ExtractionResult object
            include_content: Whether to include full table content
            
        Returns:
            Formatted string with all table structures
        """
        output = []
        output.append("=" * 80)
        output.append("TABLE STRUCTURE REPORT")
        output.append("=" * 80)
        output.append(f"\nFile: {extraction_result.pdf_path}")
        output.append(f"Backend: {extraction_result.backend.value}")
        output.append(f"Total Tables: {len(extraction_result.tables)}\n")
        
        for i, table in enumerate(extraction_result.tables, 1):
            output.append(f"\n[TABLE {i}]")
            formatted = TableStructureFormatter.format_table_structure(
                table,
                include_content=include_content
            )
            output.append(formatted)
            output.append("\n")
        
        return '\n'.join(output)


# Convenience function
def format_table_structure(table_dict: Dict[str, Any]) -> str:
    """
    Format a single table with structure information.
    
    Args:
        table_dict: Table dictionary from extraction
        
    Returns:
        Formatted string
    """
    return TableStructureFormatter.format_table_structure(table_dict)


def format_extraction_tables(extraction_result) -> str:
    """
    Format all tables from extraction result.
    
    Args:
        extraction_result: ExtractionResult object
        
    Returns:
        Formatted string
    """
    return TableStructureFormatter.format_all_tables(extraction_result)
