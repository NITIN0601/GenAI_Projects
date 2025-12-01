"""
Enhanced extraction pipeline with metadata extraction, caching, and chunking.

Features:
- Unified metadata extraction (21+ fields)
- Automatic caching for performance
- Table chunking for large tables
- VectorDB deduplication
- Progress tracking
- Robust error recovery
"""

from typing import List, Dict, Any, Optional, Callable
from pathlib import Path
import logging
import time

from extraction.unified_extractor import UnifiedExtractor
from extraction.unified_metadata_extractor import (
    UnifiedMetadataExtractor,
    extract_enhanced_metadata_unified
)
from extraction.cache import get_cache
from embeddings.table_chunker import get_table_chunker
from models.schemas import TableChunk, TableMetadata

# Import tqdm for progress bars
try:
    from tqdm import tqdm
    TQDM_AVAILABLE = True
except ImportError:
    TQDM_AVAILABLE = False

logger = logging.getLogger(__name__)



class EnhancedExtractionPipeline:
    """
    Complete extraction pipeline with caching, chunking, and metadata.
    
    Features:
    - Automatic caching (prevents re-extraction)
    - Enhanced metadata extraction (20+ fields)
    - Intelligent table chunking for RAG
    - Progress tracking with tqdm
    - Error recovery for batch processing
    - VectorDB deduplication support
    """
    
    def __init__(
        self,
        enable_caching: bool = True,
        cache_ttl_hours: int = 168,  # 7 days default
        backends: Optional[List[str]] = None,
        enable_chunking: bool = True,
        chunk_size: int = 10,
        chunk_overlap: int = 3
    ):
        """
        Initialize extraction pipeline.
        
        Args:
            enable_caching: Enable result caching
            cache_ttl_hours: Cache time-to-live in hours (default: 7 days)
            backends: List of backend names (default: ['docling'])
            enable_chunking: Enable table chunking for large tables
            chunk_size: Number of rows per chunk (default: 10)
            chunk_overlap: Number of overlapping rows (default: 3)
        """
        # Initialize extractor with caching
        self.extractor = UnifiedExtractor(
            backends=backends or ['docling'],
            enable_caching=enable_caching,
            cache_ttl_hours=cache_ttl_hours
        )
        
        self.cache_enabled = enable_caching
        self.enable_chunking = enable_chunking
        
        # Initialize chunker if enabled
        if enable_chunking:
            self.chunker = get_table_chunker(
                chunk_size=chunk_size,
                overlap=chunk_overlap
            )
        else:
            self.chunker = None
        
        logger.info(
            f"Pipeline initialized: caching={'enabled' if enable_caching else 'disabled'}, "
            f"chunking={'enabled' if enable_chunking else 'disabled'}, "
            f"ttl={cache_ttl_hours}h"
        )
    
    def extract_with_metadata(
        self,
        pdf_path: str,
        force: bool = False
    ) -> Dict[str, Any]:
        """
        Extract PDF with enhanced metadata and optional chunking.
        
        Args:
            pdf_path: Path to PDF file
            force: Force re-extraction (ignore cache)
            
        Returns:
            Dictionary with:
            - extraction_result: Original ExtractionResult
            - tables_with_metadata: List of tables with enhanced metadata
            - chunks: List of TableChunk objects (if chunking enabled)
            - cache_hit: Whether result came from cache
            - extraction_time: Time taken
            - pdf_path: Original PDF path
            - pdf_name: PDF filename
        """
        start_time = time.time()
        
        logger.info(f"Processing: {Path(pdf_path).name}")
        
        # Step 1: Extract tables (with caching)
        # The force parameter is passed to the underlying extractor
        extraction_result = self.extractor.extract(pdf_path, force=force)
        
        # Check if it was a cache hit
        cache_hit = extraction_result.extraction_time < 0.1  # Cache hits are ~0.01s
        
        if cache_hit:
            logger.info(f"✓ Cache hit for {Path(pdf_path).name}")
        else:
            logger.info(f"✓ Fresh extraction for {Path(pdf_path).name}")
        
        if not extraction_result.success:
            logger.error(f"Extraction failed for {Path(pdf_path).name}: {extraction_result.error_message}")
            # Return a structured error result
            return {
                'extraction_result': extraction_result,
                'tables_with_metadata': [],
                'chunks': [],
                'cache_hit': cache_hit,
                'extraction_time': time.time() - start_time,
                'pdf_path': pdf_path,
                'pdf_name': Path(pdf_path).name,
                'error': extraction_result.error_message
            }
        
        # Prepare PDF metadata
        if pdf_metadata is None:
            pdf_metadata = self._extract_pdf_metadata(pdf_path)
        
        # Step 2: Extract enhanced metadata using unified extractor
        logger.info(f"Extracting enhanced metadata for {len(extraction_result.tables)} tables...")
        
        tables_with_metadata_list = extract_enhanced_metadata_unified(
            extraction_result=extraction_result,
            pdf_metadata=pdf_metadata,
            extraction_backend=extraction_result.backend_used or "unknown"
        )
        
        if tables_with_metadata_list:
            logger.info(f"Enhanced metadata extracted with {len(tables_with_metadata_list[0]['metadata']) if tables_with_metadata_list else 0} fields per table")
        else:
            logger.info("No tables found for enhanced metadata extraction.")
        
        # Step 3: Chunk large tables if enabled
        all_chunks = []
        if self.enable_chunking and self.chunker:
            logger.info("Chunking large tables...")
            
            for table_data in tables_with_metadata_list:
                # Check if table needs chunking
                row_count = table_data['metadata'].get('row_count', 0)
                
                if row_count > self.chunk_size:
                    # Chunk this table
                    table_chunks = self.chunker.chunk_table(
                        content=table_data['content'],
                        metadata=TableMetadata(**table_data['metadata']), # Pass TableMetadata object
                        chunk_size=self.chunk_size,
                        overlap=self.chunk_overlap
                    )
                    all_chunks.extend(table_chunks)
                    logger.debug(f"Chunked table into {len(table_chunks)} chunks")
                else:
                    # Keep as single chunk
                    all_chunks.append(TableChunk( # Create TableChunk object
                        content=table_data['content'],
                        metadata=TableMetadata(**table_data['metadata']),
                        chunk_index=0,
                        total_chunks=1
                    ))
        else:
            # No chunking - use tables as-is, creating single TableChunk objects
            all_chunks = [
                TableChunk(
                    content=table_data['content'],
                    metadata=TableMetadata(**table_data['metadata']),
                    chunk_index=0,
                    total_chunks=1
                )
                for table_data in tables_with_metadata_list
            ]
        
        logger.info(f"Created {len(all_chunks)} chunks from {len(extraction_result.tables)} tables")
        
        total_time = time.time() - start_time
        
        logger.info(
            f"✓ Processed {len(tables_with_metadata)} tables "
            f"({len(all_chunks)} chunks) "
            f"({'cached' if cache_hit else 'extracted'}) in {total_time:.2f}s"
        )
        
        return {
            'extraction_result': extraction_result,
            'tables_with_metadata': tables_with_metadata,
            'chunks': all_chunks,  # NEW: Ready for VectorDB
            'cache_hit': cache_hit,
            'extraction_time': total_time,
            'pdf_path': pdf_path,
            'pdf_name': Path(pdf_path).name
        }
    
    def extract_batch(
        self,
        pdf_paths: List[str],
        force: bool = False,
        show_progress: bool = True,
        on_error: str = 'continue'  # 'continue', 'stop', or 'collect'
    ) -> Dict[str, Any]:
        """
        Extract multiple PDFs with enhanced metadata, progress tracking, and error recovery.
        
        Args:
            pdf_paths: List of PDF file paths
            force: Force re-extraction (ignore cache)
            show_progress: Show progress bar (requires tqdm)
            on_error: Error handling strategy:
                     'continue' - log and continue (default)
                     'stop' - raise exception
                     'collect' - collect errors and continue
            
        Returns:
            Dictionary with:
            - results: List of successful extraction results
            - errors: List of failed PDFs with error messages
            - stats: Summary statistics
        """
        results = []
        errors = []
        cache_hits = 0
        fresh_extractions = 0
        
        logger.info(f"Batch processing {len(pdf_paths)} PDFs...")
        
        # Create progress bar if available and requested
        if show_progress and TQDM_AVAILABLE:
            pdf_iterator = tqdm(pdf_paths, desc="Processing PDFs", unit="pdf")
        else:
            pdf_iterator = pdf_paths
        
        for pdf_path in pdf_iterator:
            try:
                result = self.extract_with_metadata(pdf_path, force=force)
                results.append(result)
                
                if result['cache_hit']:
                    cache_hits += 1
                else:
                    fresh_extractions += 1
                
                # Update progress bar description
                if show_progress and TQDM_AVAILABLE:
                    pdf_iterator.set_postfix({
                        'tables': len(result['tables_with_metadata']),
                        'chunks': len(result.get('chunks', [])),
                        'cached': cache_hits,
                        'fresh': fresh_extractions
                    })
                
            except Exception as e:
                error_info = {
                    'pdf_path': pdf_path,
                    'pdf_name': Path(pdf_path).name,
                    'error': str(e),
                    'error_type': type(e).__name__
                }
                
                logger.error(f"Failed to process {Path(pdf_path).name}: {e}")
                
                if on_error == 'stop':
                    raise
                elif on_error == 'collect':
                    errors.append(error_info)
                # 'continue' - just log and continue (default)
                
                if show_progress and TQDM_AVAILABLE:
                    pdf_iterator.set_postfix({'status': f'Error: {Path(pdf_path).name}'})
        
        # Calculate statistics
        total_tables = sum(len(r['tables_with_metadata']) for r in results)
        total_chunks = sum(len(r.get('chunks', [])) for r in results)
        
        stats = {
            'total_pdfs': len(pdf_paths),
            'successful': len(results),
            'failed': len(errors),
            'cache_hits': cache_hits,
            'fresh_extractions': fresh_extractions,
            'cache_hit_rate': cache_hits / len(results) * 100 if results else 0,
            'total_tables': total_tables,
            'total_chunks': total_chunks
        }
        
        # Summary
        if show_progress:
            print("\n" + "=" * 80)
            print("BATCH PROCESSING COMPLETE")
            print("=" * 80)
            print(f"Total PDFs: {stats['total_pdfs']}")
            print(f"Successful: {stats['successful']}")
            print(f"Failed: {stats['failed']}")
            print(f"Cache hits: {cache_hits} ({stats['cache_hit_rate']:.1f}%)")
            print(f"Fresh extractions: {fresh_extractions}")
            print(f"Total tables: {total_tables}")
            print(f"Total chunks: {total_chunks}")
            if errors:
                print(f"\n⚠️  Failed PDFs:")
                for err in errors:
                    print(f"   - {err['pdf_name']}: {err['error']}")
            print("=" * 80)
        
        return {
            'results': results,
            'errors': errors,
            'stats': stats
        }
    
    def check_vectordb_exists(
        self,
        vector_store,
        pdf_name: str
    ) -> bool:
        """
        Check if PDF already exists in VectorDB.
        
        Args:
            vector_store: VectorStore instance
            pdf_name: PDF filename to check
            
        Returns:
            True if document exists in VectorDB
        """
        try:
            results = vector_store.get_by_metadata(
                filters={'source_doc': pdf_name},
                limit=1
            )
            return len(results) > 0
        except Exception as e:
            logger.warning(f"Error checking VectorDB for {pdf_name}: {e}")
            return False
    
    def delete_from_vectordb(
        self,
        vector_store,
        pdf_name: str
    ) -> None:
        """
        Delete existing document from VectorDB before re-adding.
        
        Args:
            vector_store: VectorStore instance
            pdf_name: PDF filename to delete
        """
        try:
            vector_store.delete_by_source(pdf_name)
            logger.info(f"Deleted existing data for {pdf_name} from VectorDB")
        except Exception as e:
            logger.warning(f"Error deleting {pdf_name} from VectorDB: {e}")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        if self.extractor.cache:
            return self.extractor.cache.get_stats()
        return {'enabled': False}
    
    def clear_cache(self) -> int:
        """Clear extraction cache."""
        return self.extractor.clear_cache()
    
    def cleanup_expired_cache(self) -> int:
        """Remove expired cache entries."""
        if self.extractor.cache:
            return self.extractor.cache.cleanup_expired()
        return 0


# Convenience function
def extract_pdf_with_metadata(
    pdf_path: str,
    enable_caching: bool = True,
    force: bool = False
) -> Dict[str, Any]:
    """
    Quick extraction with enhanced metadata.
    
    Args:
        pdf_path: Path to PDF file
        enable_caching: Enable caching
        force: Force re-extraction
        
    Returns:
        Extraction result with enhanced metadata
    """
    pipeline = EnhancedExtractionPipeline(enable_caching=enable_caching)
    return pipeline.extract_with_metadata(pdf_path, force=force)
