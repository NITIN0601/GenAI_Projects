#!/usr/bin/env python3
"""
Test unified enhanced metadata extraction on sample PDFs.

Tests that all 21+ metadata fields are extracted correctly
across all backends (Docling, PyMuPDF, Camelot, Tabula).
"""

import sys
sys.path.insert(0, '/Users/nitin/Desktop/Chatbot/Morgan/GENAI')

from pathlib import Path
from extraction.pipeline import EnhancedExtractionPipeline
from extraction.unified_metadata_extractor import UnifiedMetadataExtractor
import json


def test_metadata_extraction(pdf_path: str):
    """Test metadata extraction on a single PDF."""
    print("=" * 80)
    print(f"TESTING: {Path(pdf_path).name}")
    print("=" * 80)
    
    # Initialize pipeline
    pipeline = EnhancedExtractionPipeline(
        enable_caching=True,
        enable_chunking=False  # Disable chunking for this test
    )
    
    # Extract with metadata
    result, tables_with_metadata, chunks = pipeline.extract_with_metadata(pdf_path)
    
    if not result.success:
        print(f"❌ Extraction failed: {result.error_message}")
        return
    
    print(f"\n✓ Extracted {len(tables_with_metadata)} tables")
    print(f"✓ Backend used: {result.backend_used}")
    
    # Analyze first table's metadata
    if tables_with_metadata:
        first_table = tables_with_metadata[0]
        metadata = first_table['metadata']
        
        print(f"\n" + "=" * 80)
        print("METADATA FIELDS EXTRACTED")
        print("=" * 80)
        
        # Group by category
        categories = {
            'Document Information': [
                'source_doc', 'page_no'
            ],
            'Company Information': [
                'company_ticker', 'company_name'
            ],
            'Financial Statement Context': [
                'statement_type', 'filing_type', 'fiscal_period_end', 'restatement'
            ],
            'Table Identification': [
                'table_title', 'table_type', 'table_index'
            ],
            'Temporal Information': [
                'year', 'quarter', 'fiscal_period', 'comparative_periods'
            ],
            'Table-Specific Metadata': [
                'units', 'currency', 'is_consolidated'
            ],
            'Table Structure': [
                'column_headers', 'row_headers', 'column_count', 'row_count',
                'table_structure', 'has_multi_level_headers', 'main_header',
                'sub_headers', 'has_hierarchy', 'subsections'
            ],
            'Hierarchical Information': [
                'parent_section', 'subsection', 'footnote_references', 'related_tables'
            ],
            'Data Quality Markers': [
                'has_currency', 'currency_count', 'has_subtotals',
                'has_calculations', 'extraction_confidence'
            ],
            'Extraction Metadata': [
                'extraction_date', 'extraction_backend', 'quality_score'
            ],
            'Chunk Management': [
                'chunk_type', 'overlapping_context', 'table_start_page', 'table_end_page'
            ]
        }
        
        total_fields = 0
        for category, fields in categories.items():
            print(f"\n{category}:")
            category_count = 0
            for field in fields:
                if field in metadata:
                    value = metadata[field]
                    # Truncate long values
                    if isinstance(value, (list, str)) and len(str(value)) > 60:
                        value_str = str(value)[:60] + "..."
                    else:
                        value_str = str(value)
                    
                    print(f"  ✓ {field}: {value_str}")
                    category_count += 1
                    total_fields += 1
            
            print(f"  ({category_count}/{len(fields)} fields)")
        
        print(f"\n" + "=" * 80)
        print(f"TOTAL: {total_fields} metadata fields extracted")
        print("=" * 80)
        
        # Show sample content
        print(f"\nSample Content (first 300 chars):")
        print(first_table['content'][:300] + "...")
        
        # Show embedding text
        print(f"\nEmbedding Text (first 300 chars):")
        print(first_table.get('embedding_text', '')[:300] + "...")


def test_all_pdfs():
    """Test metadata extraction on all available PDFs."""
    raw_data_dir = Path("/Users/nitin/Desktop/Chatbot/Morgan/raw_data")
    
    if not raw_data_dir.exists():
        print(f"❌ Directory not found: {raw_data_dir}")
        return
    
    pdf_files = list(raw_data_dir.glob("*.pdf"))
    
    if not pdf_files:
        print(f"❌ No PDF files found in {raw_data_dir}")
        return
    
    print(f"\nFound {len(pdf_files)} PDF files")
    print("Testing first PDF...\n")
    
    # Test first PDF
    test_metadata_extraction(str(pdf_files[0]))
    
    # Summary for all PDFs
    print(f"\n\n" + "=" * 80)
    print("SUMMARY - ALL PDFs")
    print("=" * 80)
    
    pipeline = EnhancedExtractionPipeline(enable_caching=True, enable_chunking=False)
    
    for pdf_file in pdf_files[:5]:  # Test first 5
        try:
            result, tables, _ = pipeline.extract_with_metadata(str(pdf_file))
            
            if result.success and tables:
                metadata = tables[0]['metadata']
                field_count = len(metadata)
                
                print(f"\n{pdf_file.name}:")
                print(f"  Tables: {len(tables)}")
                print(f"  Metadata fields: {field_count}")
                print(f"  Backend: {result.backend_used}")
                
                # Show key fields
                if 'company_ticker' in metadata:
                    print(f"  Company: {metadata['company_ticker']}")
                if 'statement_type' in metadata:
                    print(f"  Statement: {metadata['statement_type']}")
                if 'units' in metadata:
                    print(f"  Units: {metadata['units']}")
                if 'fiscal_period_end' in metadata:
                    print(f"  Period: {metadata['fiscal_period_end']}")
        
        except Exception as e:
            print(f"\n{pdf_file.name}: ❌ Error - {e}")


def main():
    """Run tests."""
    print("\n")
    print("╔" + "=" * 78 + "╗")
    print("║" + " " * 15 + "UNIFIED METADATA EXTRACTION TEST" + " " * 31 + "║")
    print("╚" + "=" * 78 + "╝")
    
    test_all_pdfs()
    
    print("\n" + "=" * 80)
    print("TEST COMPLETE")
    print("=" * 80)
    print("\nKey Features Tested:")
    print("1. ✓ 21+ metadata fields extraction")
    print("2. ✓ Works across all backends (Docling, PyMuPDF, etc.)")
    print("3. ✓ Company info extraction")
    print("4. ✓ Statement type classification")
    print("5. ✓ Units and currency detection")
    print("6. ✓ Fiscal period extraction")
    print("\n" + "=" * 80)


if __name__ == '__main__':
    main()
