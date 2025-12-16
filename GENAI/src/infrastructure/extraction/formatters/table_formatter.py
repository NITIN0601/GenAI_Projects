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
    def parse_markdown_table(markdown_content: str, title: Optional[str] = None) -> Dict[str, Any]:
        """
        Parse markdown table into structured format.
        
        Properly handles complex financial tables with:
        - Multi-level column headers (3+ levels)
        - Hierarchical row headers with parent-child relationships
        - Subsection rows (section headers within data)
        - Title rows erroneously included in content
        
        Args:
            markdown_content: Markdown table string
            title: Optional table title for validation/cleanup
            
        Returns:
            Dictionary with table structure information including:
            - columns: List of column headers (from last header row)
            - header_levels: List of all header rows for multi-level headers
            - main_headers: Combined spanning headers
            - has_multi_level_headers: Boolean
            - rows: List of data rows
            - row_headers_structured: Hierarchical row headers with indent/parent info
            - subsections: List of detected subsection titles
        """
        lines = [line.strip() for line in markdown_content.split('\n') if line.strip()]
        
        # Helper to check if a row looks like the title
        def is_title_row(row_line: str, title: str) -> bool:
            if not title:
                return False
            # Strip pipes
            content = row_line.strip('|').strip()
            # Simple fuzzy match or exact match
            from difflib import SequenceMatcher
            ratio = SequenceMatcher(None, content.lower(), title.lower()).ratio()
            return ratio > 0.8 or title.lower() in content.lower()

        # Find separator line index
        separator_idx = -1
        for i, line in enumerate(lines):
            if '|' in line and ('---' in line or '===' in line):
                separator_idx = i
                break
        
        # Separate header lines from data lines
        header_lines = []
        data_lines = []
        
        for i, line in enumerate(lines):
            if '|' not in line:
                continue
            if '---' in line or '===' in line:
                continue  # Skip separator
            
            if separator_idx == -1:
                # No separator found, treat first line as header
                if not header_lines:
                    header_lines.append(line)
                else:
                    data_lines.append(line)
            else:
                # Use separator to determine header vs data
                if i < separator_idx:
                    header_lines.append(line)
                elif i > separator_idx:
                    data_lines.append(line)
        
        # Post-processing: Check if header_lines[0] is actually the title
        # If we have a title provided and the first header line matches it
        if header_lines and title:
            # Check if first header is title
            if is_title_row(header_lines[0], title):
                # Remove it
                header_lines.pop(0)
                
                # If we have no headers left, and we have data lines, promote first data line
                # EXCEPT if there was an explicit separator, in which case empty header is weird but possible
                if not header_lines and data_lines and separator_idx == -1:
                    header_lines.append(data_lines.pop(0))
        
        # Parse header rows into header_levels
        header_levels = []
        for header_line in header_lines:
            parts = header_line.split('|')
            # Remove empty first and last elements
            if parts and not parts[0].strip():
                parts = parts[1:]
            if parts and not parts[-1].strip():
                parts = parts[:-1]
            cols = [col.strip() for col in parts]
            header_levels.append(cols)
        
        # Determine column headers and main headers
        columns = []
        main_headers = []
        has_multi_level = False
        
        if len(header_levels) == 0:
            columns = []
        elif len(header_levels) == 1:
            # Single header row - these are the column headers
            columns = header_levels[0]
        else:
            # Multi-line headers:
            # - Last row = actual column headers (sub_headers)
            # - Previous rows = main/spanning headers
            has_multi_level = True
            columns = header_levels[-1]  # Last row is the column headers
            main_headers = header_levels[:-1]  # All preceding rows are main headers
        
        # Parse data rows and detect hierarchical structure
        parsed_rows = []
        row_headers_structured = []
        subsections = []
        current_parent = None
        current_subsection = None
        current_subsection = None # Reset for safety
        
        for row_line in data_lines:
            # Split by pipe and filter out leading/trailing empty cells
            parts = row_line.split('|')
            # Remove empty first and last elements (from | at start/end)
            if parts and not parts[0].strip():
                parts = parts[1:]
            if parts and not parts[-1].strip():
                parts = parts[:-1]
            cells = [cell.strip() for cell in parts]
            parsed_rows.append(cells)
            
            if not cells:
                continue
            
            first_cell = cells[0]
            
            # Check if this is a subsection row (only first cell has content, rest empty or dashes)
            other_cells = cells[1:] if len(cells) > 1 else []
            is_subsection = first_cell and all(
                not c or c in ['-', '—', '–', ''] for c in other_cells
            ) and len(other_cells) > 0
            
            # Detect indentation level
            # Level 0: Main category (has data, or is a subsection header)
            # Level 1: Sub-item (follows a parent that ended with : or was a subsection)
            indent_level = 0
            parent_row = None
            
            if is_subsection:
                # This is a subsection/category header
                subsections.append(first_cell)
                current_subsection = first_cell
                current_parent = first_cell
                indent_level = 0
            elif current_parent:
                # Check if this looks like a sub-item
                # Patterns: "U.S.", "Non-U.S.", items under a parent ending with ":"
                if first_cell in ['U.S.', 'Non-U.S.', 'U.S', 'Non-U.S']:
                    indent_level = 1
                    parent_row = current_parent
                elif current_parent.endswith(':') or current_parent.endswith(':1') or 'Total' in first_cell:
                    # Item following a parent with colon
                    if 'Total' in first_cell:
                        indent_level = 0
                        current_parent = None
                    else:
                        indent_level = 1
                        parent_row = current_parent.rstrip(':').rstrip(':1')
                else:
                    # New main category
                    if first_cell.endswith(':'):
                        current_parent = first_cell
                    indent_level = 0
            else:
                # First item or after a Total row
                if first_cell.endswith(':'):
                    current_parent = first_cell
                indent_level = 0
            
            # Determine if this is a total/subtotal row
            is_total = 'total' in first_cell.lower() if first_cell else False
            is_subtotal = 'subtotal' in first_cell.lower() if first_cell else False
            
            row_headers_structured.append({
                'text': first_cell,
                'indent_level': indent_level,
                'parent_row': parent_row,
                'is_subsection': is_subsection,
                'is_total': is_total,
                'is_subtotal': is_subtotal,
                'subsection': current_subsection
            })
        
        return {
            'columns': columns,
            'column_count': len(columns),
            'header_levels': header_levels,
            'main_headers': main_headers,
            'has_multi_level_headers': has_multi_level,
            'rows': parsed_rows,
            'row_count': len(parsed_rows),
            'row_headers_structured': row_headers_structured,
            'subsections': subsections
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
        title = metadata.get('table_title')
        
        # Parse table with title for cleanup
        parsed = TableStructureFormatter.parse_markdown_table(content, title=title)
        
        # Build output
        output = []
        output.append("=" * 80)
        output.append(f"Table Title: {title or 'N/A'}")
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
