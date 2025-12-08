#!/usr/bin/env python3
"""
Test PDF extraction on raw_data files.
"""
import sys
from pathlib import Path
import time

# Add GENAI to path
sys.path.insert(0, '/Users/nitin/Desktop/Chatbot/Morgan/GENAI')

from extraction import UnifiedExtractor

def test_extraction():
    """Test extraction on all PDFs in raw_data."""
    
    raw_data_dir = Path('/Users/nitin/Desktop/Chatbot/Morgan/raw_data')
    pdf_files = sorted(raw_data_dir.glob('*.pdf'))
    
    print("=" * 80)
    print("📄 PDF EXTRACTION TEST")
    print("=" * 80)
    print(f"\nFound {len(pdf_files)} PDF files in raw_data/\n")
    
    # Initialize extractor
    extractor = UnifiedExtractor(
        backends=["docling", "pymupdf", "pdfplumber"],
        min_quality=60.0,
        enable_caching=True
    )
    
    results = []
    
    for i, pdf_path in enumerate(pdf_files, 1):
        print(f"\n[{i}/{len(pdf_files)}] Processing: {pdf_path.name}")
        print("-" * 80)
        
        try:
            start_time = time.time()
            result = extractor.extract(str(pdf_path))
            elapsed = time.time() - start_time
            
            # Collect results
            results.append({
                'file': pdf_path.name,
                'backend': result.backend.value,
                'quality': result.quality_score,
                'tables': len(result.tables),
                'time': elapsed,
                'success': True
            })
            
            print(f"✅ Success!")
            print(f"   Backend:  {result.backend.value}")
            print(f"   Quality:  {result.quality_score:.1f}/100")
            print(f"   Tables:   {len(result.tables)}")
            print(f"   Time:     {elapsed:.2f}s")
            
            # Show first table preview
            if result.tables:
                first_table = result.tables[0]
                content = first_table.get('content', '')
                lines = content.split('\n')[:5]  # First 5 lines
                print(f"\n   First table preview:")
                for line in lines:
                    print(f"   {line}")
                if len(content.split('\n')) > 5:
                    remaining = len(content.split('\n')) - 5
                    print(f"   ... ({remaining} more lines)")
            
        except Exception as e:
            results.append({
                'file': pdf_path.name,
                'backend': 'N/A',
                'quality': 0,
                'tables': 0,
                'time': 0,
                'success': False,
                'error': str(e)
            })
            print(f"❌ Failed: {e}")
    
    # Summary
    print("\n" + "=" * 80)
    print("📊 EXTRACTION SUMMARY")
    print("=" * 80)
    
    successful = [r for r in results if r['success']]
    failed = [r for r in results if not r['success']]
    
    print(f"\n✅ Successful: {len(successful)}/{len(results)}")
    print(f"❌ Failed:     {len(failed)}/{len(results)}")
    
    if successful:
        total_tables = sum(r['tables'] for r in successful)
        avg_quality = sum(r['quality'] for r in successful) / len(successful)
        avg_time = sum(r['time'] for r in successful) / len(successful)
        
        print(f"\n📈 Statistics:")
        print(f"   Total tables extracted: {total_tables}")
        print(f"   Average quality score:  {avg_quality:.1f}/100")
        print(f"   Average extraction time: {avg_time:.2f}s")
        
        # Backend usage
        backend_counts = {}
        for r in successful:
            backend = r['backend']
            backend_counts[backend] = backend_counts.get(backend, 0) + 1
        
        print(f"\n🔧 Backend Usage:")
        for backend, count in sorted(backend_counts.items()):
            print(f"   {backend}: {count} files")
    
    # Detailed results table
    print(f"\n📋 Detailed Results:")
    print(f"{'File':<25} {'Backend':<12} {'Quality':<10} {'Tables':<8} {'Time':<8} {'Status'}")
    print("-" * 80)
    
    for r in results:
        status = "✅ OK" if r['success'] else "❌ FAIL"
        print(f"{r['file']:<25} {r['backend']:<12} {r['quality']:<10.1f} {r['tables']:<8} {r['time']:<8.2f} {status}")
    
    if failed:
        print(f"\n❌ Failed Files:")
        for r in failed:
            print(f"   {r['file']}: {r.get('error', 'Unknown error')}")
    
    print("\n" + "=" * 80)
    print("✅ TEST COMPLETE")
    print("=" * 80)

if __name__ == '__main__':
    test_extraction()
