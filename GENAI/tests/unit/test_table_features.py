#!/usr/bin/env python3
"""
Test multi-level header and currency formatting detection.
"""
import sys
sys.path.insert(0, '/Users/nitin/Desktop/Chatbot/Morgan/GENAI')

from extraction import UnifiedExtractor, format_table_structure

def test_table_features():
    """Test specific table formatting features."""
    
    pdf_path = '/Users/nitin/Desktop/Chatbot/Morgan/raw_data/10k1222-1-20.pdf'
    
    print("=" * 80)
    print("🔍 TESTING TABLE FEATURES")
    print("=" * 80)
    
    # Extract
    extractor = UnifiedExtractor(enable_caching=True)
    result = extractor.extract(pdf_path)
    
    print(f"\nExtracted {len(result.tables)} tables\n")
    
    # Check each table for features
    for i, table in enumerate(result.tables, 1):
        content = table.get('content', '')
        metadata = table.get('metadata', {})
        
        print(f"\n{'='*80}")
        print(f"TABLE {i}: {metadata.get('table_title', 'N/A')}")
        print(f"{'='*80}")
        
        # Show raw content
        lines = content.split('\n')
        print(f"\nRaw Content (first 15 lines):")
        print("-" * 80)
        for line in lines[:15]:
            print(line)
        if len(lines) > 15:
            print(f"... ({len(lines) - 15} more lines)")
        print("-" * 80)
        
        # Check for multi-level headers
        header_lines = []
        for line in lines[:5]:  # Check first 5 lines
            if '|' in line and not line.strip().startswith('|---'):
                header_lines.append(line)
        
        print(f"\n📋 Header Analysis:")
        print(f"   Potential header rows: {len(header_lines)}")
        for j, header in enumerate(header_lines, 1):
            print(f"   Header {j}: {header[:100]}...")
        
        # Check for currency symbols
        currency_count = content.count('$')
        print(f"\n💰 Currency Analysis:")
        print(f"   $ symbols found: {currency_count}")
        
        # Find cells with $ symbol
        currency_cells = []
        for line in lines:
            if '$' in line and '|' in line:
                cells = [c.strip() for c in line.split('|')]
                for cell in cells:
                    if '$' in cell:
                        currency_cells.append(cell)
        
        if currency_cells:
            print(f"   Sample currency cells:")
            for cell in currency_cells[:5]:
                print(f"      '{cell}'")
        
        # Check for subsections (rows with only one non-empty cell)
        subsections = []
        for line in lines:
            if '|' in line and not line.strip().startswith('|---'):
                cells = [c.strip() for c in line.split('|') if c.strip()]
                if len(cells) == 1 and cells[0]:
                    subsections.append(cells[0])
        
        if subsections:
            print(f"\n📑 Potential Subsections:")
            for subsection in subsections[:3]:
                print(f"      '{subsection}'")

if __name__ == '__main__':
    test_table_features()
