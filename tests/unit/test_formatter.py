#!/usr/bin/env python3
"""
Test the new table structure formatter.
"""
import sys

from extraction import UnifiedExtractor, format_extraction_tables, format_table_structure

def test_formatter():
    """Test table structure formatting."""
    
    
    print("Testing Table Structure Formatter")
    print("=" * 80)
    
    # Extract tables
    extractor = UnifiedExtractor(enable_caching=True)
    result = extractor.extract(pdf_path)
    
    # Format all tables (without content)
    print("\n📊 ALL TABLES SUMMARY:\n")
    summary = format_extraction_tables(result)
    print(summary)
    
    # Format Table 3 (Employee Metrics) with content
    if len(result.tables) >= 3:
        print("\n" + "=" * 80)
        print("📋 DETAILED VIEW: TABLE 3 (Employee Metrics)")
        print("=" * 80)
        detailed = format_table_structure(result.tables[2])
        print(detailed)

if __name__ == '__main__':
    test_formatter()
