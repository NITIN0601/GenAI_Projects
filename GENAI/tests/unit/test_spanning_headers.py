#!/usr/bin/env python3
"""
Test centered spanning headers.
"""

from embeddings.table_chunker import TableChunker
from src.models.schemas import TableMetadata
from datetime import datetime

def test_spanning_header():
    """Test centered spanning header format"""
    print("="*70)
    print("TEST: Centered Spanning Header")
    print("="*70)
    
    table_text = """| Three Months Ended |                    |                    |
| March 31           | June 30            | September 30       |
| 2025               | 2025               | 2024               |
|--------------------|--------------------|--------------------|
| Revenue            | 100                | 110                | 105                |
| Expenses           | 80                 | 85                 | 82                 |"""
    
    print("\nINPUT:")
    print(table_text)
    
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
    chunks = chunker.chunk_table(table_text, metadata)
    
    print("\nOUTPUT:")
    print(chunks[0].content)
    
    print("\nEXPECTED:")
    print("|                    Three Months Ended                         |")
    print("| March 31 2025      | June 30 2025       | September 30 2024  |")
    print()


def test_two_column_spanning():
    """Test with 2 columns"""
    print("="*70)
    print("TEST: Two Column Spanning Header")
    print("="*70)
    
    table_text = """| Three Months Ended |                    |
| March 31, 2025     | June 30, 2025      |
|--------------------|--------------------| 
| Revenue            | 100                | 110                |
| Expenses           | 80                 | 85                 |"""
    
    print("\nINPUT:")
    print(table_text)
    
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
    chunks = chunker.chunk_table(table_text, metadata)
    
    print("\nOUTPUT:")
    print(chunks[0].content)
    
    print("\nEXPECTED:")
    print("|         Three Months Ended         |")
    print("| March 31, 2025     | June 30, 2025      |")
    print()


if __name__ == "__main__":
    test_spanning_header()
    test_two_column_spanning()
    
    print("="*70)
    print("✅ Tests complete!")
    print("="*70)
