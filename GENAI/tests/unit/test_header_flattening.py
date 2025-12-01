#!/usr/bin/env python3
"""
Test multi-line header flattening with real examples.
"""

from embeddings.table_chunker import TableChunker

def test_example_1():
    """Test: Three Months Ended with spanning header"""
    print("="*70)
    print("TEST 1: Three Months Ended (spanning header)")
    print("="*70)
    
    table_text = """| Three Months Ended |                    |
| March 31, 2025     | June 30, 2025      |
|--------------------|--------------------| 
| Revenue            | 100                | 110                |
| Expenses           | 80                 | 85                 |"""
    
    print("\nINPUT (multi-line header):")
    print(table_text)
    
    chunker = TableChunker(flatten_headers=True)
    lines = table_text.split('\n')
    header_lines, data_lines = chunker._separate_header_and_data(lines)
    
    print("\nOUTPUT (flattened header):")
    for line in header_lines:
        print(line)
    for line in data_lines[:2]:  # Show first 2 data lines
        print(line)
    
    print("\nEXPECTED:")
    print("| Three Months Ended March 31, 2025 | Three Months Ended June 30, 2025 |")
    print()


def test_example_2():
    """Test: At September/December with 3-line header"""
    print("="*70)
    print("TEST 2: At September/December (3-line header)")
    print("="*70)
    
    table_text = """| At             | At                 |
| September 30   | December 31        |
| , 2025         | , 2024             |
|----------------|--------------------| 
| Assets         | 500,000            | 480,000            |
| Liabilities    | 400,000            | 390,000            |"""
    
    print("\nINPUT (multi-line header):")
    print(table_text)
    
    chunker = TableChunker(flatten_headers=True)
    lines = table_text.split('\n')
    header_lines, data_lines = chunker._separate_header_and_data(lines)
    
    print("\nOUTPUT (flattened header):")
    for line in header_lines:
        print(line)
    for line in data_lines[:2]:  # Show first 2 data lines
        print(line)
    
    print("\nEXPECTED:")
    print("| At September 30, 2025 | At December 31, 2024 |")
    print()


def test_example_3():
    """Test: Complex spanning with empty cells"""
    print("="*70)
    print("TEST 3: Complex spanning (empty cells)")
    print("="*70)
    
    table_text = """| Three Months Ended |                    |                    |
| March 31           | June 30            | September 30       |
| 2025               | 2025               | 2024               |
|--------------------|--------------------|--------------------|
| Revenue            | 100                | 110                | 105                |"""
    
    print("\nINPUT (multi-line header):")
    print(table_text)
    
    chunker = TableChunker(flatten_headers=True)
    lines = table_text.split('\n')
    header_lines, data_lines = chunker._separate_header_and_data(lines)
    
    print("\nOUTPUT (flattened header):")
    for line in header_lines:
        print(line)
    for line in data_lines[:1]:  # Show first data line
        print(line)
    
    print("\nEXPECTED:")
    print("| Three Months Ended March 31 2025 | Three Months Ended June 30 2025 | Three Months Ended September 30 2024 |")
    print()


def test_example_4():
    """Test: Different parent headers for different columns"""
    print("="*70)
    print("TEST 4: Different parent headers")
    print("="*70)
    
    table_text = """| Assets             |                    | Liabilities        |                    |
| Current            | Non-Current        | Current            | Long-term          |
|--------------------|--------------------|--------------------|--------------------| 
| Cash               | 50,000             | -                  | -                  | -                  |"""
    
    print("\nINPUT (multi-line header):")
    print(table_text)
    
    chunker = TableChunker(flatten_headers=True)
    lines = table_text.split('\n')
    header_lines, data_lines = chunker._separate_header_and_data(lines)
    
    print("\nOUTPUT (flattened header):")
    for line in header_lines:
        print(line)
    for line in data_lines[:1]:  # Show first data line
        print(line)
    
    print("\nEXPECTED:")
    print("| Assets Current | Assets Non-Current | Liabilities Current | Liabilities Long-term |")
    print()


if __name__ == "__main__":
    test_example_1()
    test_example_2()
    test_example_3()
    test_example_4()
    
    print("="*70)
    print("✅ All tests complete!")
    print("="*70)
