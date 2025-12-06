"""
Extract Step - PDF table extraction with caching and deduplication.

Enterprise features:
- Content-hash deduplication (skip already processed PDFs)
- Extraction cache (avoid re-extracting same content)
- Parallel processing support (future)
"""

import logging
from typing import Optional, List, Dict, Any
from pathlib import Path

logger = logging.getLogger(__name__)


def run_extract(
    source_dir: Optional[str] = None,
    force: bool = False,
    deduplicator=None,
    extraction_cache=None,
):
    """
    Step 2: Extract tables from PDFs with caching.
    
    Args:
        source_dir: Directory with PDF files
        force: Force re-extraction (ignore cache)
        deduplicator: PDFDeduplicator instance (optional)
        extraction_cache: ExtractionCache instance (optional)
        
    Returns:
        PipelineResult with extracted tables
    """
    from src.pipeline import PipelineStep, PipelineResult
    from config.settings import settings
    from src.infrastructure.extraction.extractor import UnifiedExtractor as Extractor
    
    if source_dir is None:
        source_dir = settings.RAW_DATA_DIR
    
    source_path = Path(source_dir)
    if not source_path.exists():
        return PipelineResult(
            step=PipelineStep.EXTRACT,
            success=False,
            error=f"Directory {source_dir} does not exist"
        )
    
    pdf_files = list(source_path.glob("*.pdf"))
    if not pdf_files:
        return PipelineResult(
            step=PipelineStep.EXTRACT,
            success=False,
            error=f"No PDF files found in {source_dir}"
        )
    
    all_results = []
    stats = {
        'processed': 0,
        'skipped_duplicate': 0,
        'cache_hits': 0,
        'failed': 0,
        'total_tables': 0
    }
    
    try:
        extractor = Extractor(enable_caching=True)
        
        for pdf_path in pdf_files:
            # Check deduplication
            if deduplicator and not force:
                is_dup, original = deduplicator.is_duplicate(pdf_path)
                if is_dup:
                    logger.info(f"Skipping duplicate: {pdf_path.name} (matches {original})")
                    stats['skipped_duplicate'] += 1
                    continue
            
            # Check extraction cache
            content_hash = None
            if extraction_cache and not force:
                cached_result = extraction_cache.get_by_content(pdf_path)
                if cached_result:
                    logger.info(f"Extraction cache hit: {pdf_path.name}")
                    stats['cache_hits'] += 1
                    all_results.append({
                        'file': pdf_path.name,
                        'tables': cached_result.tables,
                        'metadata': cached_result.metadata,
                        'quality_score': cached_result.quality_score,
                        'from_cache': True
                    })
                    stats['total_tables'] += len(cached_result.tables)
                    continue
            
            # Extract
            result = extractor.extract(str(pdf_path))
            
            if result.is_successful():
                # Cache the result
                if extraction_cache:
                    content_hash = extraction_cache.set_by_content(pdf_path, result)
                
                # Register with deduplicator
                if deduplicator:
                    deduplicator.register(pdf_path, {
                        'content_hash': content_hash,
                        'tables': len(result.tables)
                    })
                
                all_results.append({
                    'file': pdf_path.name,
                    'tables': result.tables,
                    'metadata': result.metadata,
                    'quality_score': result.quality_score,
                    'content_hash': content_hash,
                    'from_cache': False
                })
                stats['processed'] += 1
                stats['total_tables'] += len(result.tables)
            else:
                stats['failed'] += 1
                logger.error(f"Failed to extract {pdf_path.name}: {result.error}")
        
        return PipelineResult(
            step=PipelineStep.EXTRACT,
            success=True,
            data=all_results,
            message=(
                f"Extracted {stats['total_tables']} tables from {stats['processed']} files "
                f"({stats['cache_hits']} cached, {stats['skipped_duplicate']} skipped)"
            ),
            metadata=stats
        )
    except Exception as e:
        logger.error(f"Extraction failed: {e}")
        return PipelineResult(
            step=PipelineStep.EXTRACT,
            success=False,
            error=str(e)
        )
