
import sys
import os
sys.path.insert(0, '.')

from src.extraction.formatters.metadata_extractor import MetadataExtractor
from src.models.schemas.schemas import TableMetadata
from datetime import datetime

def test_table_id_generation():
    print("Testing Table ID Generation...")
    
    # Mock table dict without table_id
    table_dict = {
        'content': '| Header 1 | Header 2 |\n|---|---|\n| Row 1 | Data 1 |',
        'metadata': {
            'source_doc': 'test_doc.pdf',
            'page_no': 5,
            'year': 2025,
            'report_type': '10-Q'
        }
    }
    
    # Extract metadata
    metadata = MetadataExtractor.extract_table_metadata(table_dict)
    
    # Check if table_id was generated
    if 'table_id' in metadata:
        print(f"✓ Table ID generated: {metadata['table_id']}")
        assert metadata['table_id'].startswith('test_doc.pdf_p5_')
    else:
        print("✗ Table ID NOT generated")
        
    # Test Schema Validation
    print("\nTesting Schema Validation...")
    try:
        # metadata already contains year, page_no, source_doc from extract_table_metadata
        table_meta = TableMetadata(
            **metadata,
            table_title="Test Table"
        )
        print(f"✓ Schema validation passed. Table ID: {table_meta.table_id}")
    except Exception as e:
        print(f"✗ Schema validation failed: {e}")

if __name__ == "__main__":
    test_table_id_generation()
