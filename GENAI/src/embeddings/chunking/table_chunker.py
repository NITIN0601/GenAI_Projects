"""
Table chunking for embeddings.

Provides chunking functionality for tables to create manageable embedding units.
"""

from typing import List, Optional, Dict, Any
from src.models.schemas import TableChunk, TableMetadata


class TableChunker:
    """Chunks tables into smaller units for embedding."""
    
    def __init__(self, chunk_size: int = 10, overlap: int = 3, flatten_headers: bool = False):
        self.chunk_size = chunk_size
        self.overlap = overlap
        self.flatten_headers = flatten_headers
        from config.settings import settings
        self.min_chunk_size = settings.MIN_CHUNK_SIZE
    
    def chunk_table(
        self,
        table_text: str,
        metadata: TableMetadata,
        table_title: str = None
    ) -> List[TableChunk]:
        """
        Create overlapping chunks from a table.
        
        Args:
            table_text: Full table text (markdown format)
            metadata: Table metadata
            table_title: Optional table title
            
        Returns:
            List of TableChunk objects with overlap
        """
        # Split table into lines
        lines = table_text.split('\n')
        
        # Separate header from data rows
        header_lines, data_lines = self._separate_header_and_data(lines)
        
        # If table is small, return as single chunk
        if len(data_lines) <= self.chunk_size:
            chunk_lines = header_lines + data_lines
            chunk_text = '\n'.join(chunk_lines)
            
            return [TableChunk(
                content=chunk_text,
                metadata=metadata,
                embedding=None
            )]
        
        # Create overlapping chunks
        chunks = []
        
        # Sliding window with overlap
        for i in range(0, len(data_lines), self.chunk_size - self.overlap):
            # Get chunk rows
            chunk_data = data_lines[i:i + self.chunk_size]
            
            # Skip if too small
            if len(chunk_data) < self.min_chunk_size:
                break
            
            # Combine header + chunk data
            chunk_lines = header_lines + chunk_data
            chunk_text = '\n'.join(chunk_lines)
            
            # Add context about chunk position
            chunk_metadata = metadata.copy() if hasattr(metadata, 'copy') else metadata
            if hasattr(chunk_metadata, 'table_title'):
                chunk_metadata.table_title = f"{metadata.table_title} (Rows {i+1}-{i+len(chunk_data)})"
            
            chunks.append(TableChunk(
                content=chunk_text,
                metadata=chunk_metadata,
                embedding=None
            ))
        
        return chunks
    
    def _separate_header_and_data(self, lines: List[str]) -> tuple:
        """Separate table header from data rows."""
        header_lines = []
        data_lines = []
        separator_idx = -1
        
        # Find the separator line (|---|---|)
        for i, line in enumerate(lines):
            if '---' in line or '===' in line:
                separator_idx = i
                break
        
        if separator_idx == -1:
            # No separator found, assume first line is header
            if lines:
                header_lines = [lines[0]]
                data_lines = lines[1:]
            return header_lines, data_lines
        
        # Everything before separator is header
        header_content_lines = lines[:separator_idx]
        separator_line = lines[separator_idx]
        
        # Process header lines
        if not self.flatten_headers:
            header_lines = header_content_lines + [separator_line]
        else:
            # Flatten multi-line headers
            if len(header_content_lines) > 1:
                flattened_header = self._flatten_multiline_header(header_content_lines)
                header_lines = [flattened_header, separator_line]
            else:
                header_lines = header_content_lines + [separator_line]
        
        # Everything after separator is data
        data_lines = [line for line in lines[separator_idx + 1:] if line.strip()]
        
        return header_lines, data_lines
    
    def _flatten_multiline_header(self, header_lines: List[str]) -> str:
        """Flatten multi-line headers into a single line."""
        if not header_lines:
            return ""
        
        # Parse each header line into columns
        all_rows = []
        for line in header_lines:
            parts = line.split('|')
            if parts and not parts[0].strip():
                parts = parts[1:]
            if parts and not parts[-1].strip():
                parts = parts[:-1]
            
            cols = [part.strip() for part in parts]
            all_rows.append(cols)
        
        if not all_rows:
            return header_lines[0]
        
        # Find max columns
        max_cols = max(len(row) for row in all_rows)
        
        # Pad rows
        for row in all_rows:
            while len(row) < max_cols:
                row.append('')
        
        # Forward-fill empty cells
        for row in all_rows:
            last_value = ''
            for col_idx in range(len(row)):
                if row[col_idx]:
                    last_value = row[col_idx]
                else:
                    row[col_idx] = last_value
        
        # Filter out spanning headers (rows with only one unique value)
        filtered_rows = []
        for row in all_rows:
            unique_values = set(v for v in row if v)
            if len(unique_values) > 1:
                filtered_rows.append(row)
        
        if not filtered_rows:
            filtered_rows = all_rows
        
        # Combine vertically for each column
        flattened_cols = []
        for col_idx in range(max_cols):
            col_values = []
            for row in filtered_rows:
                if row[col_idx]:
                    col_values.append(row[col_idx])
            flattened_col = ' '.join(col_values)
            flattened_cols.append(flattened_col)
        
        return '| ' + ' | '.join(flattened_cols) + ' |'


# Singleton instance
_table_chunker_instance = None


def get_table_chunker() -> TableChunker:
    """
    Get singleton TableChunker instance.
    
    Returns:
        TableChunker instance
    """
    global _table_chunker_instance
    if _table_chunker_instance is None:
        _table_chunker_instance = TableChunker()
    return _table_chunker_instance
