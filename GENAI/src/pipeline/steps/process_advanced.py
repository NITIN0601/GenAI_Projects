"""
Advanced processing pipeline step.

Processes files from data/processed/ and outputs to data/processed_advanced/.
Merges tables within the same sheet that share identical row labels.
"""

from typing import Optional
from src.utils import get_logger
from src.pipeline import PipelineResult, PipelineStep

logger = get_logger(__name__)


def run_process_advanced(
    source_dir: Optional[str] = None,
    dest_dir: Optional[str] = None
) -> PipelineResult:
    """
    Run advanced processing on extracted xlsx files.
    
    Merges tables within the same sheet that share identical row labels.
    
    Args:
        source_dir: Override source directory (default: data/processed)
        dest_dir: Override destination directory (default: data/processed_advanced)
        
    Returns:
        PipelineResult with processing outcome
    """
    try:
        from src.infrastructure.extraction.exporters.table_merger import get_table_merger
        
        merger = get_table_merger()
        
        # Override directories if provided
        if source_dir:
            from pathlib import Path
            merger.source_dir = Path(source_dir)
        
        if dest_dir:
            from pathlib import Path
            merger.dest_dir = Path(dest_dir)
            merger.dest_dir.mkdir(parents=True, exist_ok=True)
        
        # Process all files
        results = merger.process_all_files()
        
        if results['errors']:
            error_msg = f"Processed with {len(results['errors'])} errors: {results['errors']}"
            logger.warning(error_msg)
        
        return PipelineResult(
            step=PipelineStep.PROCESS_ADVANCED,
            success=True,
            message=f"Processed {results['files_processed']} files, merged {results['total_tables_merged']} tables",
            data={
                'files_processed': results['files_processed'],
                'files_with_merges': results['files_with_merges'],
                'tables_merged': results['total_tables_merged'],
                'output_files': results['output_files'],
                'errors': results['errors']
            },
            metadata={
                'source_dir': str(merger.source_dir),
                'dest_dir': str(merger.dest_dir)
            }
        )
        
    except Exception as e:
        logger.error(f"Advanced processing failed: {e}", exc_info=True)
        return PipelineResult(
            step=PipelineStep.PROCESS_ADVANCED,
            success=False,
            error=str(e)
        )
