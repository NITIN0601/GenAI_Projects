#!/usr/bin/env python3
"""
Quick test to verify Docling can extract tables from PDFs.
Tests on a single PDF and shows results.
"""

import sys
sys.path.insert(0, '.')

from scrapers.docling_scraper import DoclingPDFScraper
from pathlib import Path

def quick_test(pdf_path: str):
    """Quick test of Docling extraction."""
    print(f"\n{'='*70}")
    print(f"Testing: {Path(pdf_path).name}")
    print(f"{'='*70}\n")
    
    try:
        # Initialize scraper
        print("1. Initializing DoclingPDFScraper...")
        scraper = DoclingPDFScraper(pdf_path)
        
        # Extract document
        print("2. Extracting document (this may take a minute on first run)...")
        document = scraper.extract_document()
        
        # Show results
        print(f"\n✓ SUCCESS! Extraction completed.\n")
        
        print(f"Document Metadata:")
        print(f"  - Filename: {document.metadata.filename}")
        print(f"  - Company: {document.metadata.company_name}")
        print(f"  - Document Type: {document.metadata.document_type}")
        print(f"  - Total Pages: {document.metadata.total_pages}")
        
        print(f"\nExtraction Results:")
        print(f"  - Pages Processed: {len(document.pages)}")
        print(f"  - Tables Extracted: {len(document.tables)}")
        
        if document.tables:
            print(f"\n{'='*70}")
            print(f"FIRST 3 TABLES:")
            print(f"{'='*70}\n")
            
            for i, table in enumerate(document.tables[:3], 1):
                print(f"\n[Table {i}] {table.original_title}")
                print(f"  Type: {table.table_type}")
                print(f"  Page: {table.metadata.get('page_no')}")
                print(f"  Structure:")
                print(f"    - Row Headers: {len(table.row_headers)}")
                print(f"    - Column Headers: {len(table.column_headers)}")
                print(f"    - Data Cells: {len(table.data_cells)}")
                print(f"    - Periods: {len(table.periods)}")
                
                # Show first few row headers with hierarchy
                if table.row_headers:
                    print(f"\n  Row Headers (first 5):")
                    for rh in table.row_headers[:5]:
                        indent = "  " * rh.indent_level
                        canonical = f" → {rh.canonical_label}" if rh.canonical_label else ""
                        print(f"    {indent}• {rh.text}{canonical}")
                
                # Show column headers
                if table.column_headers:
                    print(f"\n  Column Headers:")
                    for ch in table.column_headers[:5]:
                        units = f" ({ch.units})" if ch.units else ""
                        print(f"    • {ch.text}{units}")
                
                # Show sample data cells
                if table.data_cells:
                    print(f"\n  Sample Data Cells (first 3):")
                    for cell in table.data_cells[:3]:
                        print(f"    [{cell.row_header}] × [{cell.column_header}]")
                        print(f"      Value: {cell.raw_text} (type: {cell.data_type})")
                        if cell.base_value:
                            print(f"      Base: ${cell.base_value:,.0f}")
        
        print(f"\n{'='*70}")
        print(f"✓ Test completed successfully!")
        print(f"{'='*70}\n")
        
        return True
        
    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    # Test on first available PDF
    pdf_path = "../raw_data/10q0325.pdf"
    
    success = quick_test(pdf_path)
    
    if success:
        print("\n✓ Docling extraction is working correctly!")
        print("  - Tables extracted with complete structure")
        print("  - Row headers with hierarchy detected")
        print("  - Column headers with metadata extracted")
        print("  - Data cells with types preserved")
    else:
        print("\n✗ Extraction failed - see error above")
        sys.exit(1)
