#!/usr/bin/env python3
"""
Test enhanced table formatter.
"""
import sys
sys.path.insert(0, '/Users/nitin/Desktop/Chatbot/Morgan/GENAI')

from extraction import UnifiedExtractor, format_all_tables_enhanced, format_enhanced_table

def test_enhanced_formatter():
    """Test enhanced table formatting."""
    
    pdf_path = '/Users/nitin/Desktop/Chatbot/Morgan/raw_data/10k1222-1-20.pdf'
    
    print("=" * 80)
    print("🚀 TESTING ENHANCED TABLE FORMATTER")
    print("=" * 80)
    
    # Extract
    extractor = UnifiedExtractor(enable_caching=True)
    result = extractor.extract(pdf_path)
    
    # Format all tables with enhanced detection
    print("\n📊 ALL TABLES (Enhanced Format):\n")
    enhanced = format_all_tables_enhanced(result)
    print(enhanced)
    
    # Show detailed view of Table 4 (has currency)
    if len(result.tables) >= 4:
        print("\n" + "=" * 80)
        print("💰 DETAILED VIEW: TABLE 4 (with currency)")
        print("=" * 80)
        detailed = format_enhanced_table(result.tables[3])
        print(detailed)

if __name__ == '__main__':
    test_enhanced_formatter()
