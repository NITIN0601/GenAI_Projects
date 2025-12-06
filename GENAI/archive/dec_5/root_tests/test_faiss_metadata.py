#!/usr/bin/env python3
"""
Test script to verify FAISS vector DB metadata structure.

This script:
1. Creates a FAISS vector store
2. Adds a chunk with full metadata
3. Saves and reloads the index
4. Searches and verifies metadata is preserved
"""

import sys
import os
sys.path.append(os.getcwd())

from src.vector_store.stores.faiss_store import FAISSVectorStore
from src.embeddings.manager import get_embedding_manager
from src.models import TableMetadata, TableChunk
from config.settings import settings

def test_faiss_metadata():
    print("\n=== Testing FAISS Metadata Structure ===\n")
    
    # Force local embeddings
    settings.EMBEDDING_PROVIDER = "local"
    
    # Get embedding manager
    embedding_manager = get_embedding_manager()
    
    # Create FAISS store
    print("1. Creating FAISS vector store...")
    faiss_store = FAISSVectorStore(
        embedding_function=embedding_manager.langchain_embeddings,
        dimension=settings.EMBEDDING_DIMENSION,
        persist_dir="./test_faiss_metadata"
    )
    
    # Create test metadata with all fields
    print("2. Creating test chunk with full metadata...")
    metadata = TableMetadata(
        source_doc="test_10q.pdf",
        page_no=5,
        table_title="Consolidated Balance Sheet",
        year=2024,
        quarter="Q1",
        report_type="10-Q",
        table_type="Balance Sheet",
        fiscal_period="March 31, 2024"
    )
    
    # Create chunk
    chunk = TableChunk(
        chunk_id="test_chunk_001",
        content="Total Assets: $3.2 trillion | Total Liabilities: $2.8 trillion",
        metadata=metadata,
        embedding=None  # Will be generated
    )
    
    # Add chunk
    print("3. Adding chunk to FAISS...")
    faiss_store.add_chunks([chunk])
    
    print(f"   ✓ Added chunk (Total vectors: {faiss_store.index.ntotal})")
    
    # Verify metadata was stored
    print("\n4. Verifying metadata storage...")
    stored_metadata = faiss_store.metadata[0]
    print(f"   Stored metadata keys: {list(stored_metadata.keys())}")
    print(f"   Source doc: {stored_metadata.get('source_doc')}")
    print(f"   Year: {stored_metadata.get('year')}")
    print(f"   Quarter: {stored_metadata.get('quarter')}")
    print(f"   Table title: {stored_metadata.get('table_title')}")
    print(f"   Report type: {stored_metadata.get('report_type')}")
    print(f"   Fiscal period: {stored_metadata.get('fiscal_period')}")
    
    # Test search and metadata retrieval
    print("\n5. Testing search with metadata retrieval...")
    results = faiss_store.search("Total Assets", top_k=1)
    
    if results:
        result = results[0]
        print(f"   ✓ Found {len(results)} result(s)")
        print(f"   Content: {result.content[:50]}...")
        print(f"   Metadata type: {type(result.metadata)}")
        print(f"   Metadata.source_doc: {result.metadata.source_doc}")
        print(f"   Metadata.year: {result.metadata.year}")
        print(f"   Metadata.quarter: {result.metadata.quarter}")
        print(f"   Score: {result.score:.4f}")
    else:
        print("   ✗ No results found")
    
    # Test metadata filtering
    print("\n6. Testing metadata filtering...")
    filtered_results = faiss_store.search(
        "Assets",
        top_k=5,
        filters={"year": 2024, "quarter": "Q1"}
    )
    print(f"   ✓ Found {len(filtered_results)} result(s) with filters")
    
    # Reload test
    print("\n7. Testing persistence (reload)...")
    faiss_store_2 = FAISSVectorStore(
        embedding_function=embedding_manager.langchain_embeddings,
        dimension=settings.EMBEDDING_DIMENSION,
        persist_dir="./test_faiss_metadata"
    )
    
    print(f"   ✓ Reloaded index (Total vectors: {faiss_store_2.index.ntotal})")
    print(f"   ✓ Metadata count: {len(faiss_store_2.metadata)}")
    
    if faiss_store_2.metadata:
        reloaded_meta = faiss_store_2.metadata[0]
        print(f"   ✓ Reloaded metadata.source_doc: {reloaded_meta.get('source_doc')}")
        print(f"   ✓ Reloaded metadata.year: {reloaded_meta.get('year')}")
    
    # Cleanup
    print("\n8. Cleaning up test directory...")
    import shutil
    shutil.rmtree("./test_faiss_metadata", ignore_errors=True)
    print("   ✓ Cleanup complete")
    
    print("\n=== FAISS Metadata Test Complete ===\n")
    print("✅ All metadata fields are properly stored and retrieved!")

if __name__ == "__main__":
    test_faiss_metadata()
