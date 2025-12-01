#!/usr/bin/env python3
"""
Quick extraction script using Docling backend only.

Based on test results showing Docling performs best for financial PDFs.
"""
import sys
sys.path.insert(0, '/Users/nitin/Desktop/Chatbot/Morgan/GENAI')

from extraction import UnifiedExtractor

def main():
    """Extract using Docling backend only."""
    
    # Initialize with Docling only (best performance)
    extractor = UnifiedExtractor(
        backends=['docling'],  # Use only Docling
        min_quality=60.0,
        enable_caching=True,
        cache_ttl_hours=168  # 7 days cache for financial reports
    )
    
    # Example: Extract a PDF
    pdf_path = '/Users/nitin/Desktop/Chatbot/Morgan/raw_data/10k1222.pdf'
    
    print("=" * 80)
    print("🚀 DOCLING-ONLY EXTRACTION")
    print("=" * 80)
    print(f"\nExtracting: {pdf_path}")
    print("Backend: Docling (best for financial PDFs)")
    print("Cache: Enabled (7 days TTL)\n")
    
    # Extract
    result = extractor.extract(pdf_path)
    
    # Show results
    print("\n" + "=" * 80)
    print("📊 RESULTS")
    print("=" * 80)
    print(f"Backend Used: {result.backend.value}")
    print(f"Quality Score: {result.quality_score:.1f}/100")
    print(f"Tables Found: {len(result.tables)}")
    print(f"Extraction Time: {result.extraction_time:.2f}s")
    print(f"Pages: {result.page_count}")
    
    if result.tables:
        print(f"\n📋 First Table Preview:")
        print("-" * 80)
        first_table = result.tables[0]['content']
        lines = first_table.split('\n')
        for line in lines[:10]:
            print(line)
        if len(lines) > 10:
            print(f"... ({len(lines) - 10} more lines)")
    
    print("\n" + "=" * 80)
    print("✅ EXTRACTION COMPLETE")
    print("=" * 80)
    
    # Show cache stats
    cache_stats = extractor.cache.get_stats()
    print(f"\n💾 Cache Stats:")
    print(f"   Total cached files: {cache_stats['total_files']}")
    print(f"   Cache size: {cache_stats['total_size_mb']:.1f} MB")
    print(f"   TTL: {cache_stats['ttl_hours']} hours")

if __name__ == '__main__':
    main()
