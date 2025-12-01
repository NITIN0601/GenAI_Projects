#!/usr/bin/env python3
"""
Debug why spanning headers aren't being formatted.
"""

from embeddings.table_chunker import TableChunker
from src.models.schemas import TableMetadata
from datetime import datetime

def debug_chunking():
    """Debug the chunking process step by step"""
    
    table_text = """| Three Months Ended |                    |                    |
| March 31           | June 30            | September 30       |
| 2025               | 2025               | 2024               |
|--------------------|--------------------|--------------------|
| Revenue            | 100                | 110                | 105                |
| Expenses           | 80                 | 85                 | 82                 |"""
    
    print("INPUT TABLE:")
    print(table_text)
    print("\n" + "="*70 + "\n")
    
    metadata = TableMetadata(
        source_doc="test.pdf",
        page_no=1,
        table_title="Test Table",
        year=2025,
        quarter="Q1",
        report_type="10-Q",
        extraction_date=datetime.now()
    )
    
    chunker = TableChunker(flatten_headers=False)
    
    # Step 1: Split into lines
    lines = table_text.split('\n')
    print("STEP 1: Lines split:")
    for i, line in enumerate(lines):
        print(f"  {i}: {line}")
    print()
    
    # Step 2: Separate headers and data
    header_lines, data_lines = chunker._separate_header_and_data(lines)
    print("STEP 2: After _separate_header_and_data:")
    print("  Header lines:")
    for i, line in enumerate(header_lines):
        print(f"    {i}: {line}")
    print("  Data lines:")
    for i, line in enumerate(data_lines):
        print(f"    {i}: {line}")
    print()
    
    # Step 3: Create chunk
    chunks = chunker.chunk_table(table_text, metadata)
    print("STEP 3: Final chunk content:")
    print(chunks[0].content)
    print()

if __name__ == "__main__":
    debug_chunking()
