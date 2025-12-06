"""
Complete Data Processing Pipeline Example
==========================================

This script demonstrates the full end-to-end pipeline:
1. Extract tables from PDFs (with caching)
2. Generate embeddings
3. Store in vector database (ChromaDB/FAISS/Redis)

All configurable via .env file!
"""

import sys
from pathlib import Path
from typing import List
import logging

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import components
from config.settings import settings, print_config
from src.infrastructure.extraction.extractor import UnifiedExtractor
from src.infrastructure.embeddings.manager import get_embedding_manager
from src.infrastructure.vectordb.manager import get_vectordb_manager
from src.models.schemas import TableChunk, TableMetadata


def main():
    """Run complete data processing pipeline."""
    
    # ========================================================================
    # STEP 1: Show Current Configuration
    # ========================================================================
    print("\n" + "="*80)
    print("GENAI DATA PROCESSING PIPELINE")
    print("="*80)
    
    print_config()
    
    # ========================================================================
    # STEP 2: Initialize Components
    # ========================================================================
    print("\n📦 Initializing components...")
    
    # Extraction (reads EXTRACTION_BACKEND from .env)
    extractor = UnifiedExtractor()
    logger.info(f"✓ Extractor initialized with backend: {settings.EXTRACTION_BACKEND}")
    
    # Embeddings (reads EMBEDDING_PROVIDER from .env)
    embedding_manager = get_embedding_manager()
    logger.info(f"✓ Embedding manager initialized: {settings.EMBEDDING_PROVIDER}")
    
    # Vector Store (reads VECTORDB_PROVIDER from .env)
    vector_store = get_vectordb_manager()
    logger.info(f"✓ Vector store initialized: {settings.VECTORDB_PROVIDER}")
    
    # ========================================================================
    # STEP 3: Extract Tables from PDFs
    # ========================================================================
    print("\n📄 Extracting tables from PDFs...")
    
    # Get PDF files
    pdf_dir = Path(settings.LEGACY_RAW_DATA_DIR)  # or settings.RAW_DATA_DIR
    pdf_files = list(pdf_dir.glob("*.pdf"))
    
    if not pdf_files:
        logger.error(f"No PDF files found in {pdf_dir}")
        return
    
    logger.info(f"Found {len(pdf_files)} PDF files")
    
    all_chunks = []
    
    for pdf_file in pdf_files:
        logger.info(f"\nProcessing: {pdf_file.name}")
        
        try:
            # Extract (uses cache automatically!)
            result = extractor.extract(str(pdf_file))
            
            if not result.is_successful():
                logger.error(f"  ✗ Extraction failed: {result.error}")
                continue
            
            logger.info(f"  ✓ Extracted {len(result.tables)} tables")
            logger.info(f"  ✓ Quality score: {result.quality_score:.1f}")
            logger.info(f"  ✓ Backend used: {result.backend.value}")
            
            # Convert tables to chunks
            for i, table in enumerate(result.tables):
                # Create metadata
                metadata = TableMetadata(
                    source_doc=pdf_file.name,
                    page_no=table.get('metadata', {}).get('page_no', 1),
                    table_title=table.get('metadata', {}).get('table_title', f'Table {i+1}'),
                    year=result.metadata.get('year'),
                    quarter=result.metadata.get('quarter'),
                    report_type=result.metadata.get('report_type')
                )
                
                # Create chunk
                chunk = TableChunk(
                    content=table.get('content', ''),
                    metadata=metadata,
                    embedding=None  # Will be generated next
                )
                
                all_chunks.append(chunk)
            
        except Exception as e:
            logger.error(f"  ✗ Error processing {pdf_file.name}: {e}")
            continue
    
    logger.info(f"\n✓ Total chunks created: {len(all_chunks)}")
    
    if not all_chunks:
        logger.error("No chunks to process!")
        return
    
    # ========================================================================
    # STEP 4: Generate Embeddings
    # ========================================================================
    print("\n🧮 Generating embeddings...")
    
    for i, chunk in enumerate(all_chunks):
        try:
            # Generate embedding for chunk content
            embedding = embedding_manager.generate_embedding(chunk.content)
            chunk.embedding = embedding
            
            if (i + 1) % 10 == 0:
                logger.info(f"  Generated {i+1}/{len(all_chunks)} embeddings")
                
        except Exception as e:
            logger.error(f"  ✗ Error generating embedding for chunk {i}: {e}")
            continue
    
    # Count successful embeddings
    chunks_with_embeddings = [c for c in all_chunks if c.embedding is not None]
    logger.info(f"✓ Generated {len(chunks_with_embeddings)} embeddings")
    
    # ========================================================================
    # STEP 5: Store in Vector Database
    # ========================================================================
    print("\n💾 Storing in vector database...")
    
    try:
        # Add chunks to vector store
        vector_store.add_chunks(chunks_with_embeddings, show_progress=True)
        
        logger.info(f"✓ Stored {len(chunks_with_embeddings)} chunks in {settings.VECTORDB_PROVIDER}")
        
    except Exception as e:
        logger.error(f"✗ Error storing in vector database: {e}")
        return
    
    # ========================================================================
    # STEP 6: Verify Storage
    # ========================================================================
    print("\n🔍 Verifying storage...")
    
    try:
        # Get stats
        stats = vector_store.get_stats()
        logger.info(f"✓ Vector DB Stats:")
        logger.info(f"  - Total chunks: {stats.get('total_chunks', 'N/A')}")
        logger.info(f"  - Provider: {stats.get('provider', 'N/A')}")
        
        # Test search
        test_query = "revenue"
        results = vector_store.search(test_query, top_k=3)
        logger.info(f"\n✓ Test search for '{test_query}':")
        for i, result in enumerate(results[:3], 1):
            # result is now a SearchResult object
            logger.info(f"  {i}. {result.metadata.table_title}")
        
    except Exception as e:
        logger.error(f"✗ Error verifying storage: {e}")
    
    # ========================================================================
    # STEP 7: Summary
    # ========================================================================
    print("\n" + "="*80)
    print("PIPELINE COMPLETE! ✅")
    print("="*80)
    print(f"\n📊 Summary:")
    print(f"  - PDFs processed: {len(pdf_files)}")
    print(f"  - Tables extracted: {len(all_chunks)}")
    print(f"  - Embeddings generated: {len(chunks_with_embeddings)}")
    print(f"  - Stored in: {settings.VECTORDB_PROVIDER}")
    print(f"  - Extraction backend: {settings.EXTRACTION_BACKEND}")
    print(f"  - Embedding provider: {settings.EMBEDDING_PROVIDER}")
    print(f"\n✓ Data is ready for querying!")
    print("="*80 + "\n")


if __name__ == "__main__":
    main()
