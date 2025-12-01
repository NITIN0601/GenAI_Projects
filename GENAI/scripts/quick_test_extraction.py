#!/usr/bin/env python3
"""
Quick test to verify table extraction is working.
"""

from docling.document_converter import DocumentConverter
from docling_core.types.doc import DocItemLabel
from pathlib import Path

def quick_test(pdf_path):
    print(f"\n{'='*70}")
    print(f"Testing: {Path(pdf_path).name}")
    print(f"{'='*70}\n")
    
    # Convert PDF
    print("Converting PDF with Docling...")
    converter = DocumentConverter()
    result = converter.convert(pdf_path)
    doc = result.document
    
    print(f"[OK] Conversion complete")
    print(f"  Total pages: {len(doc.pages)}")
    
    # Count items
    all_items = list(doc.iterate_items())
    print(f"  Total items: {len(all_items)}")
    
    # Count by label
    label_counts = {}
    for item in all_items:
        label = str(item.label)
        label_counts[label] = label_counts.get(label, 0) + 1
    
    print(f"\n  Label breakdown:")
    for label, count in sorted(label_counts.items()):
        print(f"    {label}: {count}")
    
    # Extract tables
    tables = [item for item in all_items if item.label == DocItemLabel.TABLE]
    print(f"\n[OK] Found {len(tables)} tables")
    
    if tables:
        print(f"\n  First 5 tables:")
        for i, table in enumerate(tables[:5], 1):
            caption = table.caption if hasattr(table, 'caption') else "No caption"
            page_no = 1
            if hasattr(table, 'prov') and table.prov:
                for p in table.prov:
                    if hasattr(p, 'page_no'):
                        page_no = p.page_no
                        break
            
            print(f"    {i}. Page {page_no}: {caption[:60]}...")
    
    print(f"\n{'='*70}\n")
    return len(tables)

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        pdf_path = sys.argv[1]
    else:
        pdf_path = "../raw_data/10k1222.pdf"
    
    tables_found = quick_test(pdf_path)
    print(f"Result: {tables_found} tables extracted")
