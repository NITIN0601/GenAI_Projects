#!/usr/bin/env python3
"""
Test table structure detection and formatting.
"""
import sys
from pathlib import Path

sys.path.insert(0, '/Users/nitin/Desktop/Chatbot/Morgan/GENAI')

from extraction import UnifiedExtractor

def analyze_table_structure():
    """Analyze table structure in detail."""
    
    pdf_path = '/Users/nitin/Desktop/Chatbot/Morgan/raw_data/10k1222-1-20.pdf'
    
    print("=" * 80)
    print("📊 TABLE STRUCTURE ANALYSIS")
    print("=" * 80)
    
    # Extract with caching
    extractor = UnifiedExtractor(enable_caching=True)
    result = extractor.extract(pdf_path)
    
    print(f"\nFile: {Path(pdf_path).name}")
    print(f"Backend: {result.backend.value}")
    print(f"Total Tables: {len(result.tables)}\n")
    
    # Focus on Table 3 (Employee Metrics)
    for i, table in enumerate(result.tables, 1):
        metadata = table.get('metadata', {})
        content = table.get('content', '')
        
        print("=" * 80)
        print(f"TABLE {i}: {metadata.get('table_title', 'N/A')}")
        print("=" * 80)
        
        # Parse table structure
        lines = content.split('\n')
        
        # Find header row
        header_line = None
        data_lines = []
        
        for line in lines:
            if '|' in line and line.strip():
                if header_line is None and not line.strip().startswith('|---'):
                    header_line = line
                elif not line.strip().startswith('|---'):
                    data_lines.append(line)
        
        # Extract columns
        if header_line:
            columns = [col.strip() for col in header_line.split('|') if col.strip()]
            print(f"\n📋 Table Header:")
            print(f"   Columns: {columns}")
            print(f"   Column Count: {len(columns)}")
        
        print(f"\n📏 Table Size:")
        print(f"   Rows: {len(data_lines)}")
        print(f"   Columns: {len(columns) if header_line else 'N/A'}")
        
        # Show structure
        print(f"\n📄 Table Content:")
        print("-" * 80)
        for line in lines[:25]:  # First 25 lines
            print(line)
        if len(lines) > 25:
            print(f"... ({len(lines) - 25} more lines)")
        print("-" * 80)
        
        # Analyze row headers
        print(f"\n🔍 Row Header Analysis:")
        row_headers = []
        for line in data_lines[:10]:  # First 10 data rows
            cells = [cell.strip() for cell in line.split('|') if cell.strip()]
            if cells:
                row_headers.append(cells[0] if cells else '')
        
        # Check for hierarchical structure
        has_hierarchy = any(not header for header in row_headers)
        print(f"   Hierarchical Structure: {'Yes' if has_hierarchy else 'No'}")
        print(f"   Sample Row Headers:")
        for j, header in enumerate(row_headers[:5], 1):
            print(f"      Row {j}: '{header}'")
        
        # Check for spanning cells
        print(f"\n📐 Structure Features:")
        print(f"   Empty cells (potential spanning): {content.count('||')}")
        print(f"   Total cells: ~{len(data_lines) * len(columns) if header_line else 'N/A'}")
        
        print("\n")

if __name__ == '__main__':
    analyze_table_structure()
