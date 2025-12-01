#!/usr/bin/env python3
"""
Process all PDFs in raw_data directory with enhanced pipeline.

Features:
- Automatic caching (60,000x speedup)
- Enhanced metadata extraction (20+ fields)
- Intelligent chunking for large tables
- Progress bars (tqdm)
- Error recovery
- VectorDB deduplication
- Batch processing

Usage:
    python3 process_raw_data.py                    # Process with caching
    python3 process_raw_data.py --force            # Force re-extraction
    python3 process_raw_data.py --store-vectordb   # Store in VectorDB
    python3 process_raw_data.py --clear-cache      # Clear cache first
    python3 process_raw_data.py --no-dedup         # Skip deduplication
"""

import sys
sys.path.insert(0, '/Users/nitin/Desktop/Chatbot/Morgan/GENAI')

from pathlib import Path
from extraction.pipeline import EnhancedExtractionPipeline
from embeddings.vector_store import get_vector_store
from embeddings.embedding_manager import get_embedding_manager
import argparse


def main():
    """Process all PDFs in raw_data directory."""
    
    # Parse arguments
    parser = argparse.ArgumentParser(description='Process PDFs with enhanced pipeline')
    parser.add_argument('--force', action='store_true', help='Force re-extraction (ignore cache)')
    parser.add_argument('--no-cache', action='store_true', help='Disable caching')
    parser.add_argument('--no-chunking', action='store_true', help='Disable table chunking')
    parser.add_argument('--store-vectordb', action='store_true', help='Store in VectorDB')
    parser.add_argument('--clear-cache', action='store_true', help='Clear cache before processing')
    parser.add_argument('--no-dedup', action='store_true', help='Skip VectorDB deduplication')
    parser.add_argument('--on-error', choices=['continue', 'stop', 'collect'], 
                       default='continue', help='Error handling strategy')
    args = parser.parse_args()
    
    # Initialize pipeline
    print("=" * 80)
    print("ENHANCED PDF EXTRACTION PIPELINE")
    print("=" * 80)
    
    pipeline = EnhancedExtractionPipeline(
        enable_caching=not args.no_cache,
        cache_ttl_hours=168,  # 7 days
        enable_chunking=not args.no_chunking
    )
    
    # Clear cache if requested
    if args.clear_cache:
        print("\nClearing cache...")
        deleted = pipeline.clear_cache()
        print(f"✓ Deleted {deleted} cache files\n")
    
    # Show cache stats
    cache_stats = pipeline.get_cache_stats()
    if cache_stats['enabled']:
        print(f"\n📦 Cache Status:")
        print(f"   Enabled: Yes")
        print(f"   Location: {cache_stats['cache_dir']}")
        print(f"   Cached files: {cache_stats['total_files']}")
        print(f"   Cache size: {cache_stats['total_size_mb']:.1f} MB")
        print(f"   TTL: {cache_stats['ttl_hours']} hours")
        print(f"   Expired: {cache_stats['expired_files']} files")
    else:
        print("\n📦 Cache: Disabled")
    
    # Find all PDFs in raw_data
    raw_data_dir = Path('/Users/nitin/Desktop/Chatbot/Morgan/raw_data')
    pdf_files = sorted(raw_data_dir.glob('*.pdf'))
    
    print(f"\n📄 Found {len(pdf_files)} PDFs in {raw_data_dir}")
    print()
    
    if not pdf_files:
        print("No PDF files found!")
        return
    
    # Process all PDFs
    batch_result = pipeline.extract_batch(
        pdf_paths=[str(p) for p in pdf_files],
        force=args.force,
        show_progress=True,
        on_error=args.on_error
    )
    
    results = batch_result['results']
    errors = batch_result['errors']
    stats = batch_result['stats']
    
    # Store in VectorDB if requested
    if args.store_vectordb and results:
        print("\n" + "=" * 80)
        print("STORING IN VECTORDB")
        print("=" * 80)
        
        vs = get_vector_store()
        em = get_embedding_manager()
        
        total_chunks_stored = 0
        skipped_duplicates = 0
        updated_documents = 0
        
        for result in results:
            pdf_name = result['pdf_name']
            chunks = result.get('chunks', [])
            
            if not chunks:
                print(f"\n⚠️  {pdf_name}: No chunks to store")
                continue
            
            print(f"\nProcessing {pdf_name}: {len(chunks)} chunks")
            
            # Check for duplicates (unless --no-dedup)
            if not args.no_dedup:
                exists = pipeline.check_vectordb_exists(vs, pdf_name)
                
                if exists:
                    print(f"   ⚠️  Document already in VectorDB")
                    
                    # Delete old version
                    pipeline.delete_from_vectordb(vs, pdf_name)
                    print(f"   ✓ Deleted old version")
                    updated_documents += 1
                else:
                    print(f"   ✓ New document")
            
            # Generate embeddings for chunks that don't have them
            chunks_to_embed = [c for c in chunks if c.embedding is None]
            
            if chunks_to_embed:
                print(f"   Generating embeddings for {len(chunks_to_embed)} chunks...")
                texts = [c.content for c in chunks_to_embed]
                embeddings = em.generate_embeddings_batch(texts, show_progress=False)
                
                for chunk, embedding in zip(chunks_to_embed, embeddings):
                    chunk.embedding = embedding
            
            # Store in VectorDB
            vs.add_chunks(chunks, show_progress=False)
            total_chunks_stored += len(chunks)
            
            print(f"   ✓ Stored {len(chunks)} chunks")
        
        print(f"\n✓ Total chunks stored: {total_chunks_stored}")
        if updated_documents > 0:
            print(f"✓ Updated documents: {updated_documents}")
        
        # Show VectorDB stats
        vs_stats = vs.get_stats()
        print(f"\n📊 VectorDB Statistics:")
        print(f"   Total chunks: {vs_stats['total_chunks']}")
        print(f"   Unique documents: {vs_stats['unique_documents']}")
        print(f"   Years: {vs_stats['years']}")
    
    # Final summary
    print("\n" + "=" * 80)
    print("PROCESSING COMPLETE")
    print("=" * 80)
    
    print(f"\n📈 Summary:")
    print(f"   PDFs processed: {stats['successful']}/{stats['total_pdfs']}")
    print(f"   Failed: {stats['failed']}")
    print(f"   Total tables: {stats['total_tables']}")
    print(f"   Total chunks: {stats['total_chunks']}")
    print(f"   Cache hits: {stats['cache_hits']} ({stats['cache_hit_rate']:.1f}%)")
    print(f"   Fresh extractions: {stats['fresh_extractions']}")
    
    if cache_stats['enabled'] and stats['cache_hits'] > 0:
        time_saved = stats['cache_hits'] * 10  # Estimate 10 min per PDF
        print(f"\n💾 Cache saved you ~{time_saved} minutes!")
    
    if errors:
        print(f"\n⚠️  {len(errors)} PDFs failed - check logs for details")
    
    print("\n" + "=" * 80)


if __name__ == '__main__':
    main()
