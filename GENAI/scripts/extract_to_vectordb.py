#!/usr/bin/env python3
"""
End-to-end pipeline: Extract PDF → Generate Embeddings → Store in VectorDB

This script demonstrates the complete flow from PDF extraction to vector storage.
"""
import sys
sys.path.insert(0, '/Users/nitin/Desktop/Chatbot/Morgan/GENAI')

from extraction import UnifiedExtractor
from embeddings.table_chunker import get_table_chunker
from embeddings.embedding_manager import get_embedding_manager
from embeddings.vector_store import get_vector_store
from src.models.schemas import TableChunk, TableMetadata


def extract_to_vectordb(pdf_path: str, show_progress: bool = True):
    """
    Complete pipeline: PDF → Extraction → Chunking → Embedding → VectorDB
    
    Args:
        pdf_path: Path to PDF file
        show_progress: Show progress bars
    """
    print("=" * 80)
    print("🚀 EXTRACTION → VECTORDB PIPELINE")
    print("=" * 80)
    print(f"\nPDF: {pdf_path}\n")
    
    # Step 1: Extract tables with Docling
    print("📄 Step 1: Extracting tables from PDF...")
    extractor = UnifiedExtractor(backends=['docling'])
    result = extractor.extract(pdf_path)
    
    print(f"   ✅ Extracted {len(result.tables)} tables")
    print(f"   Quality: {result.quality_score:.1f}/100")
    print(f"   Time: {result.extraction_time:.2f}s\n")
    
    if not result.tables:
        print("❌ No tables found!")
        return
    
    # Step 2: Chunk tables
    print("✂️  Step 2: Chunking tables...")
    chunker = get_table_chunker(chunk_size=10, overlap=3)
    
    all_chunks = []
    for i, table in enumerate(result.tables, 1):
        # Create metadata from extraction result
        metadata = TableMetadata(
            source_doc=table['metadata']['source_doc'],
            page_no=table['metadata']['page_no'],
            table_title=table['metadata']['table_title'],
            year=table['metadata']['year'],
            quarter=table['metadata'].get('quarter'),
            report_type=table['metadata']['report_type']
        )
        
        # Chunk the table
        chunks = chunker.chunk_table(
            table_text=table['content'],
            metadata=metadata
        )
        
        all_chunks.extend(chunks)
        
        if show_progress and i % 10 == 0:
            print(f"   Processed {i}/{len(result.tables)} tables...")
    
    print(f"   ✅ Created {len(all_chunks)} chunks\n")
    
    # Step 3: Generate embeddings
    print("🧠 Step 3: Generating embeddings...")
    em = get_embedding_manager()
    
    # Extract text from chunks
    texts = [chunk.content for chunk in all_chunks]
    
    # Generate embeddings in batch (much faster!)
    embeddings = em.generate_embeddings_batch(texts, show_progress=show_progress)
    
    # Attach embeddings to chunks
    for chunk, embedding in zip(all_chunks, embeddings):
        chunk.embedding = embedding
    
    print(f"   ✅ Generated {len(embeddings)} embeddings")
    print(f"   Dimension: {len(embeddings[0])}D\n")
    
    # Step 4: Store in VectorDB
    print("💾 Step 4: Storing in ChromaDB...")
    vs = get_vector_store()
    
    vs.add_chunks(all_chunks, show_progress=show_progress)
    
    print(f"   ✅ Stored {len(all_chunks)} chunks in vector database\n")
    
    # Step 5: Show stats
    print("=" * 80)
    print("📊 PIPELINE COMPLETE")
    print("=" * 80)
    
    stats = vs.get_stats()
    print(f"\n📈 Vector Store Statistics:")
    print(f"   Total chunks: {stats['total_chunks']}")
    print(f"   Unique documents: {stats['unique_documents']}")
    print(f"   Years: {stats['years']}")
    print(f"   Sources: {len(stats['sources'])} PDFs")
    
    # Test search
    print(f"\n🔍 Testing semantic search...")
    test_query = "What are the total assets?"
    search_results = vs.search(test_query, top_k=3)
    
    print(f"\nQuery: '{test_query}'")
    print(f"Results: {len(search_results)} chunks found\n")
    
    for i, res in enumerate(search_results, 1):
        print(f"Result {i}:")
        print(f"  Source: {res['metadata']['source_doc']}")
        print(f"  Page: {res['metadata']['page_no']}")
        print(f"  Title: {res['metadata']['table_title']}")
        print(f"  Year: {res['metadata']['year']}")
        if 'quarter' in res['metadata']:
            print(f"  Quarter: {res['metadata']['quarter']}")
        print(f"  Content preview: {res['content'][:150]}...")
        print()
    
    print("=" * 80)
    print("✅ SUCCESS - Tables are now searchable in VectorDB!")
    print("=" * 80)


def batch_process_pdfs(pdf_paths: list):
    """
    Process multiple PDFs in batch.
    
    Args:
        pdf_paths: List of PDF file paths
    """
    print("=" * 80)
    print("🔄 BATCH PROCESSING")
    print("=" * 80)
    print(f"\nProcessing {len(pdf_paths)} PDFs...\n")
    
    for i, pdf_path in enumerate(pdf_paths, 1):
        print(f"\n[{i}/{len(pdf_paths)}] Processing: {pdf_path}")
        print("-" * 80)
        
        try:
            extract_to_vectordb(pdf_path, show_progress=False)
        except Exception as e:
            print(f"❌ Error: {e}")
            continue
    
    print("\n" + "=" * 80)
    print("✅ BATCH PROCESSING COMPLETE")
    print("=" * 80)
    
    # Final stats
    vs = get_vector_store()
    stats = vs.get_stats()
    
    print(f"\n📊 Final Statistics:")
    print(f"   Total chunks: {stats['total_chunks']}")
    print(f"   Unique documents: {stats['unique_documents']}")
    print(f"   Years covered: {stats['years']}")
    print(f"   Documents: {stats['sources']}")


if __name__ == '__main__':
    # Example 1: Single PDF
    pdf_path = '/Users/nitin/Desktop/Chatbot/Morgan/raw_data/10k1222.pdf'
    extract_to_vectordb(pdf_path)
    
    # Example 2: Batch processing (uncomment to use)
    # pdf_paths = [
    #     '/Users/nitin/Desktop/Chatbot/Morgan/raw_data/10k1220.pdf',
    #     '/Users/nitin/Desktop/Chatbot/Morgan/raw_data/10k1221.pdf',
    #     '/Users/nitin/Desktop/Chatbot/Morgan/raw_data/10k1222.pdf',
    # ]
    # batch_process_pdfs(pdf_paths)
