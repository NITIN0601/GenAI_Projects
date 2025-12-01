"""
Table chunking for large financial tables.

Handles intelligent chunking with:
- Semantic boundaries (preserve table structure)
- Overlap for context
- Header preservation
- Metadata tracking
"""

from typing import List, Dict, Any, Optional
import logging

from src.models.schemas import TableMetadata
from vectordb.schemas import TableChunk, EnhancedTableMetadata
from config.settings import settings

logger = logging.getLogger(__name__)


class TableChunker:
    """
    Intelligent chunking for financial tables with overlap.
    
    Ensures vector search can find relevant information even when
    it spans multiple rows or sections.
    """
    
    def __init__(
        self,
        chunk_size: int = 10,  # Number of rows per chunk
        overlap: int = 3,       # Number of overlapping rows
        min_chunk_size: int = 3, # Minimum rows in a chunk
        flatten_headers: bool = False  # Keep multi-line headers as-is (don't flatten)
    ):
        """
        Initialize chunker.
        
        Args:
            chunk_size: Target number of rows per chunk
            overlap: Number of rows to overlap between chunks
            min_chunk_size: Minimum rows for a valid chunk
            flatten_headers: If True, flatten multi-line headers to single line
        """
        self.chunk_size = chunk_size
        self.overlap = overlap
        self.min_chunk_size = min_chunk_size
        self.flatten_headers = flatten_headers
    
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
        
        # If table is small, return as single chunk (but use formatted headers!)
        if len(data_lines) <= self.chunk_size:
            # Reconstruct table with formatted headers
            chunk_lines = header_lines + data_lines
            chunk_text = '\n'.join(chunk_lines)
            
            return [TableChunk(
                content=chunk_text,
                metadata=metadata,
                embedding=None
            )]
        
        # Create overlapping chunks
        chunks = []
        
        # Strategy 1: Sliding window with overlap
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
            chunk_metadata = metadata.copy()
            chunk_metadata.table_title = f"{metadata.table_title} (Rows {i+1}-{i+len(chunk_data)})"
            
            chunks.append(TableChunk(
                content=chunk_text,
                metadata=chunk_metadata,
                embedding=None
            ))
        
        return chunks
    
    def chunk_table_by_sections(
        self,
        table_text: str,
        metadata: TableMetadata,
        section_markers: List[str] = None
    ) -> List[TableChunk]:
        """
        Chunk table by logical sections (e.g., "Assets", "Liabilities").
        
        Args:
            table_text: Full table text
            metadata: Table metadata
            section_markers: Keywords that indicate section boundaries
        
        Returns:
            List of chunks split by sections with overlap
        """
        if section_markers is None:
            # Common financial statement sections
            section_markers = [
                'assets', 'liabilities', 'equity',
                'revenues', 'expenses', 'income',
                'operating', 'financing', 'investing',
                'total', 'subtotal'
            ]
        
        lines = table_text.split('\n')
        header_lines, data_lines = self._separate_header_and_data(lines)
        
        # Find section boundaries
        sections = self._find_sections(data_lines, section_markers)
        
        if not sections:
            # No sections found, fall back to sliding window
            return self.chunk_table(table_text, metadata)
        
        chunks = []
        
        for i, (section_name, start_idx, end_idx) in enumerate(sections):
            # Add overlap with previous section
            overlap_start = max(0, start_idx - self.overlap)
            
            # Add overlap with next section
            overlap_end = min(len(data_lines), end_idx + self.overlap)
            
            # Get section data
            section_data = data_lines[overlap_start:overlap_end]
            
            # Combine header + section
            chunk_lines = header_lines + section_data
            chunk_text = '\n'.join(chunk_lines)
            
            # Update metadata
            chunk_metadata = metadata.copy()
            chunk_metadata.table_title = f"{metadata.table_title} - {section_name}"
            
            chunks.append(TableChunk(
                content=chunk_text,
                metadata=chunk_metadata,
                embedding=None
            ))
        
        return chunks
    
    def chunk_with_context(
        self,
        table_text: str,
        metadata: TableMetadata,
        context_before: int = 2,
        context_after: int = 2
    ) -> List[TableChunk]:
        """
        Create chunks where each row has context from surrounding rows.
        
        Useful for queries like "What was revenue?" where the answer
        might need context from parent/child rows.
        
        Args:
            table_text: Full table text
            metadata: Table metadata
            context_before: Rows of context before each row
            context_after: Rows of context after each row
        
        Returns:
            List of chunks with contextual overlap
        """
        lines = table_text.split('\n')
        header_lines, data_lines = self._separate_header_and_data(lines)
        
        chunks = []
        
        for i, line in enumerate(data_lines):
            # Get context window
            start = max(0, i - context_before)
            end = min(len(data_lines), i + context_after + 1)
            
            # Get context lines
            context_lines = data_lines[start:end]
            
            # Combine header + context
            chunk_lines = header_lines + context_lines
            chunk_text = '\n'.join(chunk_lines)
            
            # Update metadata
            chunk_metadata = metadata.copy()
            chunk_metadata.table_title = f"{metadata.table_title} (Row {i+1} with context)"
            
            chunks.append(TableChunk(
                content=chunk_text,
                metadata=chunk_metadata,
                embedding=None
            ))
        
        return chunks
    
    def _separate_header_and_data(self, lines: List[str]) -> tuple:
        """
        Separate table header from data rows.
        
        Handles multi-line headers intelligently:
        - Detects spanning headers (rows with only one unique value)
        - Formats spanning headers as centered across all columns
        - Preserves other header rows as-is
        - Preserves markdown table structure
        
        Example:
            Input:
                | Three Months Ended |                    |                    |
                | March 31           | June 30            | September 30       |
                | 2025               | 2025               | 2024               |
            
            Output:
                |                    Three Months Ended                         |
                | March 31 2025      | June 30 2025       | September 30 2024  |
        """
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
            # Keep multi-line headers but format spanning headers
            processed_headers = self._format_spanning_headers(header_content_lines)
            header_lines = processed_headers + [separator_line]
        else:
            # Flatten multi-line headers (existing logic)
            if len(header_content_lines) > 1:
                flattened_header = self._flatten_multiline_header(header_content_lines)
                header_lines = [flattened_header, separator_line]
            else:
                header_lines = header_content_lines + [separator_line]
        
        # Everything after separator is data
        data_lines = [line for line in lines[separator_idx + 1:] if line.strip()]
        
        return header_lines, data_lines
    
    def _format_spanning_headers(self, header_lines: List[str]) -> List[str]:
        """
        Format spanning headers (rows with only one unique value) as centered.
        Also flattens non-spanning rows together.
        
        Example:
            Input:
                | Three Months Ended |                    |                    |
                | March 31           | June 30            | September 30       |
                | 2025               | 2025               | 2024               |
            
            Output:
                |                    Three Months Ended                         |
                | March 31 2025      | June 30 2025       | September 30 2024  |
        """
        if not header_lines:
            return header_lines
        
        # Parse each header line into columns
        all_rows = []
        for line in header_lines:
            parts = line.split('|')
            # Remove first and last empty parts
            if parts and not parts[0].strip():
                parts = parts[1:]
            if parts and not parts[-1].strip():
                parts = parts[:-1]
            
            cols = [part.strip() for part in parts]
            all_rows.append(cols)
        
        if not all_rows:
            return header_lines
        
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
        
        # Separate spanning rows from non-spanning rows
        spanning_rows = []
        non_spanning_rows = []
        
        for row in all_rows:
            unique_values = set(v for v in row if v)
            
            if len(unique_values) == 1 and unique_values:
                # Spanning header
                spanning_rows.append(row)
            else:
                # Non-spanning header (multiple different values)
                non_spanning_rows.append(row)
        
        # Format output
        formatted_lines = []
        
        # Add spanning headers (centered)
        for row in spanning_rows:
            spanning_text = list(set(v for v in row if v))[0]
            # Calculate total width (approximate)
            col_width = 20  # Approximate column width
            total_width = col_width * max_cols + (max_cols - 1) * 3  # 3 for " | "
            centered_text = spanning_text.center(total_width)
            formatted_line = f"|{centered_text}|"
            formatted_lines.append(formatted_line)
        
        # Flatten non-spanning rows (combine vertically per column)
        if non_spanning_rows:
            flattened_cols = []
            for col_idx in range(max_cols):
                col_values = []
                for row in non_spanning_rows:
                    if row[col_idx]:
                        col_values.append(row[col_idx])
                flattened_col = ' '.join(col_values)
                flattened_cols.append(flattened_col)
            
            formatted_line = '| ' + ' | '.join(flattened_cols) + ' |'
            formatted_lines.append(formatted_line)
        
        return formatted_lines
    
    def _flatten_multiline_header(self, header_lines: List[str]) -> str:
        """
        Flatten multi-line headers into a single line.
        
        Correctly handles column-spanning headers where parent headers
        apply to multiple child columns.
        
        KEY RULE: If a header row has only ONE unique value (same value across all columns),
                  it's a SPANNING HEADER that should be SKIPPED (not included in output).
        
        Example 1 (SKIP first row):
            Input:
                | Three Months Ended |                    |
                | March 31, 2025     | June 30, 2025      |
            
            Output (CORRECT):
                | March 31, 2025 | June 30, 2025 |
            
            Logic: Row 1 has only "Three Months Ended" (spanning) → SKIP IT
                   Row 2 has different values → USE IT
        
        Example 2 (SKIP first row):
            Input:
                | Three Months Ended |                    |                    |
                | March 31           | June 30            | September 30       |
                | 2025               | 2025               | 2024               |
            
            Output (CORRECT):
                | March 31 2025 | June 30 2025 | September 30 2024 |
            
            Logic: Row 1 has only "Three Months Ended" (spanning) → SKIP IT
                   Row 2 has different values → USE IT
                   Row 3 has different values → USE IT
        
        Example 3 (USE all rows - different values):
            Input:
                | At             | At                 |
                | September 30   | December 31        |
                | , 2025         | , 2024             |
            
            Output (CORRECT):
                | At September 30, 2025 | At December 31, 2024 |
            
            Logic: Row 1 has "At" in BOTH columns (different positions) → USE IT
                   Row 2 has different values → USE IT
                   Row 3 has different values → USE IT
        
        Example 4 (USE all rows - different parent headers):
            Input:
                | Assets             |                    | Liabilities        |                    |
                | Current            | Non-Current        | Current            | Long-term          |
            
            Output (CORRECT):
                | Assets Current | Assets Non-Current | Liabilities Current | Liabilities Long-term |
            
            Logic: Row 1 has "Assets" and "Liabilities" (different) → USE IT
                   Row 2 has different values → USE IT
        
        Algorithm:
            1. Parse all header rows into columns
            2. For each row, forward-fill empty cells from left (column spanning)
            3. Check if row has only ONE unique value → SKIP (it's a spanning header)
            4. For remaining rows, combine values vertically for each column
        """
        if not header_lines:
            return ""
        
        # Parse each header line into columns
        all_rows = []
        for line in header_lines:
            # Split by | and clean
            parts = line.split('|')
            # Remove first and last empty parts (from leading/trailing |)
            if parts and not parts[0].strip():
                parts = parts[1:]
            if parts and not parts[-1].strip():
                parts = parts[:-1]
            
            cols = [part.strip() for part in parts]
            all_rows.append(cols)
        
        if not all_rows:
            return header_lines[0]
        
        # Find the maximum number of columns
        max_cols = max(len(row) for row in all_rows)
        
        # Pad all rows to have the same number of columns
        for row in all_rows:
            while len(row) < max_cols:
                row.append('')
        
        # Forward-fill empty cells in each row (column spanning)
        # When a cell is empty, it inherits the value from the left
        for row in all_rows:
            last_value = ''
            for col_idx in range(len(row)):
                if row[col_idx]:
                    # Non-empty cell, update last_value
                    last_value = row[col_idx]
                else:
                    # Empty cell, inherit from left
                    row[col_idx] = last_value
        
        # Filter out rows that have only ONE unique value (spanning headers)
        filtered_rows = []
        for row in all_rows:
            unique_values = set(v for v in row if v)
            if len(unique_values) > 1:
                # Multiple different values → keep this row
                filtered_rows.append(row)
            # else: Only one value (spanning header) → skip it
        
        # If all rows were filtered out, use the original
        if not filtered_rows:
            filtered_rows = all_rows
        
        # Now combine vertically for each column
        flattened_cols = []
        
        for col_idx in range(max_cols):
            # Collect values for this column from filtered rows
            col_values = []
            
            for row in filtered_rows:
                cell_value = row[col_idx]
                if cell_value:
                    col_values.append(cell_value)
            
            # Join with space
            flattened_col = ' '.join(col_values)
            flattened_cols.append(flattened_col)
        
        # Reconstruct markdown table row
        return '| ' + ' | '.join(flattened_cols) + ' |'
    
    def _find_sections(
        self,
        lines: List[str],
        section_markers: List[str]
    ) -> List[tuple]:
        """
        Find section boundaries in table.
        
        Returns:
            List of (section_name, start_idx, end_idx) tuples
        """
        sections = []
        current_section = None
        section_start = 0
        
        for i, line in enumerate(lines):
            line_lower = line.lower()
            
            # Check if this line starts a new section
            for marker in section_markers:
                if marker in line_lower:
                    # Save previous section
                    if current_section:
                        sections.append((current_section, section_start, i))
                    
                    # Start new section
                    current_section = line.strip()
                    section_start = i
                    break
        
        # Add final section
        if current_section:
            sections.append((current_section, section_start, len(lines)))
        
        return sections


def create_chunked_embeddings(
    table_text: str,
    metadata: TableMetadata,
    chunking_strategy: str = "sliding_window",
    chunk_size: int = 10,
    overlap: int = 3
) -> List[TableChunk]:
    """
    Convenience function to create chunks with specified strategy.
    
    Args:
        table_text: Full table text
        metadata: Table metadata
        chunking_strategy: "sliding_window", "sections", or "context"
        chunk_size: Number of rows per chunk
        overlap: Number of overlapping rows
    
    Returns:
        List of TableChunk objects
    """
    chunker = TableChunker(chunk_size=chunk_size, overlap=overlap)
    
    if chunking_strategy == "sliding_window":
        return chunker.chunk_table(table_text, metadata)
    elif chunking_strategy == "sections":
        return chunker.chunk_table_by_sections(table_text, metadata)
    elif chunking_strategy == "context":
        return chunker.chunk_with_context(table_text, metadata)
    else:
        raise ValueError(f"Unknown chunking strategy: {chunking_strategy}")


# Singleton instance
_chunker: Optional[TableChunker] = None

def get_table_chunker(
    chunk_size: int = 10,
    overlap: int = 3
) -> TableChunker:
    """Get or create singleton table chunker."""
    global _chunker
    if _chunker is None:
        _chunker = TableChunker(chunk_size=chunk_size, overlap=overlap)
    return _chunker
