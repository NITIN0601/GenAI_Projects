"""
Advanced processing pipeline step.

Processes files from data/processed/ and outputs to data/processed_advanced/.
Merges tables within the same sheet that share identical row labels.

Implements StepInterface for consistency with other pipeline steps.
"""

from pathlib import Path
from typing import Dict, Any, Optional

from src.pipeline.base import StepInterface, StepResult, StepStatus, PipelineContext
from src.pipeline import PipelineResult, PipelineStep
from src.utils import get_logger

logger = get_logger(__name__)


class ProcessAdvancedStep(StepInterface):
    """
    Advanced processing step - merge tables with identical row labels.
    
    Implements StepInterface (like ExtractStep, EmbedStep pattern).
    
    Reads: data/processed/ xlsx files
    Writes: data/processed_advanced/ xlsx files
    """
    
    name = "process_advanced"
    
    def __init__(self, source_dir: Optional[str] = None, dest_dir: Optional[str] = None):
        """
        Initialize step with optional directory overrides.
        
        Args:
            source_dir: Override source directory (default: data/processed)
            dest_dir: Override destination directory (default: data/processed_advanced)
        """
        self.source_dir = source_dir
        self.dest_dir = dest_dir
    
    def validate(self, context: PipelineContext) -> bool:
        """Validate that source directory exists and has xlsx files."""
        from src.core import get_paths
        
        paths = get_paths()
        source_path = Path(self.source_dir) if self.source_dir else Path(paths.data_dir) / "processed"
        
        if not source_path.exists():
            logger.warning(f"Source directory does not exist: {source_path}")
            return False
        
        xlsx_files = list(source_path.glob("*_tables.xlsx"))
        if not xlsx_files:
            logger.warning(f"No xlsx files in {source_path}")
            return False
        
        return True
    
    def get_step_info(self) -> Dict[str, Any]:
        """Get step metadata."""
        return {
            "name": self.name,
            "description": "Merge tables with identical row labels within same sheet",
            "reads": ["data/processed/*.xlsx"],
            "writes": ["data/processed_advanced/*.xlsx"],
            "source_dir": self.source_dir,
            "dest_dir": self.dest_dir
        }
    
    def execute(self, context: PipelineContext) -> StepResult:
        """Execute advanced processing."""
        try:
            from src.infrastructure.extraction.exporters.table_merger import get_table_merger
            
            merger = get_table_merger()
            
            # Override directories if provided
            if self.source_dir:
                merger.source_dir = Path(self.source_dir)
            
            if self.dest_dir:
                merger.dest_dir = Path(self.dest_dir)
                merger.dest_dir.mkdir(parents=True, exist_ok=True)
            
            # Process all files
            results = merger.process_all_files()
            
            if results['errors']:
                logger.warning(f"Processed with {len(results['errors'])} errors")
            
            return StepResult(
                step_name=self.name,
                status=StepStatus.SUCCESS,
                data={
                    'files_processed': results['files_processed'],
                    'files_with_merges': results['files_with_merges'],
                    'tables_merged': results['total_tables_merged'],
                    'output_files': results['output_files'],
                    'errors': results['errors']
                },
                message=f"Processed {results['files_processed']} files, merged {results['total_tables_merged']} tables",
                metadata={
                    'source_dir': str(merger.source_dir),
                    'dest_dir': str(merger.dest_dir)
                }
            )
            
        except Exception as e:
            logger.error(f"Advanced processing failed: {e}", exc_info=True)
            return StepResult(
                step_name=self.name,
                status=StepStatus.FAILED,
                error=str(e)
            )


# Backward-compatible function for main.py CLI
def run_process_advanced(
    source_dir: Optional[str] = None,
    dest_dir: Optional[str] = None
) -> PipelineResult:
    """
    Run advanced processing on extracted xlsx files.
    
    Legacy wrapper maintaining backward compatibility with main.py CLI.
    
    Merges tables within the same sheet that share identical row labels.
    
    Args:
        source_dir: Override source directory (default: data/processed)
        dest_dir: Override destination directory (default: data/processed_advanced)
        
    Returns:
        PipelineResult with processing outcome
    """
    step = ProcessAdvancedStep(source_dir=source_dir, dest_dir=dest_dir)
    ctx = PipelineContext()
    
    # Skip validation failure - just run with defaults
    if not step.validate(ctx):
        logger.warning("Validation failed, but continuing with step execution")
    
    result = step.execute(ctx)
    
    return PipelineResult(
        step=PipelineStep.PROCESS_ADVANCED,
        success=result.success,
        data=result.data,
        message=result.message,
        error=result.error,
        metadata=result.metadata
    )
