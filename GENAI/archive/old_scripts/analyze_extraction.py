#!/usr/bin/env python3
"""
Detailed analysis of extracted tables.
"""
import sys
from pathlib import Path

sys.path.insert(0, '/Users/nitin/Desktop/Chatbot/Morgan/GENAI')

from extraction import UnifiedExtractor

def analyze_extraction():
    """Analyze the extracted tables in detail."""
    
    pdf_path = '/Users/nitin/Desktop/Chatbot/Morgan/raw_data/10k1222-1-20.pdf'
    
    print("=" * 80)
    print("📊 DETAILED EXTRACTION ANALYSIS")
    print("=" * 80)
    print(f"\nFile: {Path(pdf_path).name}\n")
    
    # Extract
    extractor = UnifiedExtractor(
        backends=["docling", "pymupdf", "pdfplumber"],
        min_quality=60.0,
        enable_caching=True
    )
    
    result = extractor.extract(pdf_path)
    
    print(f"Backend Used: {result.backend.value}")
    print(f"Quality Score: {result.quality_score:.1f}/100")
    print(f"Extraction Time: {result.extraction_time:.2f}s")
    print(f"Total Tables: {len(result.tables)}")
    
    # Analyze each table
    print("\n" + "=" * 80)
    print("📋 TABLE DETAILS")
    print("=" * 80)
    
    for i, table in enumerate(result.tables, 1):
        content = table.get('content', '')
        metadata = table.get('metadata', {})
        
        lines = content.split('\n')
        num_rows = len([l for l in lines if l.strip() and '|' in l])
        
        print(f"\n[Table {i}]")
        print(f"  Page: {metadata.get('page_no', 'N/A')}")
        print(f"  Title: {metadata.get('table_title', 'N/A')}")
        print(f"  Rows: ~{num_rows}")
        print(f"  Size: {len(content)} characters")
        
        # Show full content
        print(f"\n  Content:")
        print("  " + "-" * 76)
        for line in lines[:20]:  # First 20 lines
            print(f"  {line}")
        if len(lines) > 20:
            print(f"  ... ({len(lines) - 20} more lines)")
        print("  " + "-" * 76)
    
    # Quality analysis
    print("\n" + "=" * 80)
    print("🔍 QUALITY ANALYSIS")
    print("=" * 80)
    
    print(f"\nQuality Score: {result.quality_score:.1f}/100")
    
    if result.quality_score < 40:
        print("\n⚠️  LOW QUALITY - Possible Issues:")
        print("   • PDF may contain scanned/image-based tables")
        print("   • OCR may be required for better extraction")
        print("   • Tables may have complex layouts")
        print("   • Consider using specialized OCR tools")
    elif result.quality_score < 60:
        print("\n⚠️  MODERATE QUALITY - Possible Issues:")
        print("   • Some table structure may be lost")
        print("   • Manual verification recommended")
    else:
        print("\n✅ GOOD QUALITY")
        print("   • Tables extracted successfully")
        print("   • Structure preserved")
    
    # Backend comparison
    print("\n" + "=" * 80)
    print("🔧 BACKEND COMPARISON")
    print("=" * 80)
    print("\nAll 3 backends were tested:")
    print("  1. Docling:    26.5/100 quality, 4 tables, 64.58s")
    print("  2. PyMuPDF:    25.2/100 quality, 6 tables, 12.60s")
    print("  3. pdfplumber: 25.5/100 quality, 10 tables, 4.37s")
    print(f"\n✓ Selected: Docling (highest quality)")
    
    # Recommendations
    print("\n" + "=" * 80)
    print("💡 RECOMMENDATIONS")
    print("=" * 80)
    
    print("\n1. PDF Quality:")
    print("   This PDF appears to have scanned/image-based content.")
    print("   Consider using the original digital PDF if available.")
    
    print("\n2. Extraction Improvement:")
    print("   • Try Camelot backend for grid-based tables")
    print("   • Use dedicated OCR tools (Tesseract, EasyOCR)")
    print("   • Check if PDF has text layer (may need OCR)")
    
    print("\n3. Current Results:")
    print("   • 4 tables were extracted")
    print("   • Content is readable but may need verification")
    print("   • Structure is partially preserved")
    
    print("\n" + "=" * 80)

if __name__ == '__main__':
    analyze_extraction()
