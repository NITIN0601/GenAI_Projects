"""
Extract Step - PDF table extraction.

Implements StepInterface following system architecture pattern.
"""

from pathlib import Path
from typing import Dict, Any
from tqdm import tqdm

from src.pipeline.base import StepInterface, StepResult, StepStatus, PipelineContext
from src.utils import get_logger

logger = get_logger(__name__)


class ExtractStep(StepInterface):
    """
    Extract tables from PDF files.
    
    Implements StepInterface (like VectorDBInterface pattern).
    
    Reads: context.source_dir
    Writes: context.extracted_data
    """
    
    name = "extract"
    

    def __init__(self, enable_caching: bool = True, force: bool = False):
        self.enable_caching = enable_caching
        self.force = force
    
    def validate(self, context: PipelineContext) -> bool:
        """Validate source directory exists."""
        from config.settings import settings
        
        source_dir = context.source_dir or settings.RAW_DATA_DIR
        source_path = Path(source_dir)
        
        if not source_path.exists():
            logger.error(f"Source directory does not exist: {source_dir}")
            return False
        
        pdf_files = list(source_path.glob("*.pdf"))
        if not pdf_files:
            logger.error(f"No PDF files in {source_dir}")
            return False
        
        return True
    
    def get_step_info(self) -> Dict[str, Any]:
        """Get step metadata."""
        return {
            "name": self.name,
            "description": "Extract tables from PDF files using Docling",
            "reads": ["context.source_dir"],
            "writes": ["context.extracted_data"],
            "caching_enabled": self.enable_caching,
            "force_extraction": self.force
        }
    
    def execute(self, context: PipelineContext) -> StepResult:
        """Extract tables from PDFs."""
        from config.settings import settings
        from src.infrastructure.extraction.extractor import UnifiedExtractor
        
        source_dir = context.source_dir or settings.RAW_DATA_DIR
        source_path = Path(source_dir)
        pdf_files = list(source_path.glob("*.pdf"))
        
        all_results = []
        stats = {
            'processed': 0,
            'failed': 0,
            'total_tables': 0
        }
        
        try:
            extractor = UnifiedExtractor(enable_caching=self.enable_caching)
            
            pbar = tqdm(
                total=len(pdf_files),
                desc="📄 Extracting",
                unit="file",
                ncols=80,
                bar_format='{desc}: {percentage:3.0f}%|{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]'
            )
            
            for pdf_path in pdf_files:
                pbar.set_description(f"📄 {pdf_path.name[:25]}")
                
                # Pass force flag to extractor
                result = extractor.extract(str(pdf_path), force=self.force)
                
                if result.is_successful():
                    all_results.append({
                        'file': pdf_path.name,
                        'tables': result.tables,
                        'metadata': result.metadata,
                        'quality_score': result.quality_score,
                    })
                    stats['processed'] += 1
                    stats['total_tables'] += len(result.tables)
                else:
                    stats['failed'] += 1
                    logger.error(f"Failed: {pdf_path.name}: {result.error}")
                
                pbar.update(1)
            
            pbar.set_description("📄 Extraction Complete")
            pbar.close()
            
            # Write to context for next step
            context.extracted_data = all_results
            
            return StepResult(
                step_name=self.name,
                status=StepStatus.SUCCESS,
                data=all_results,
                message=f"Extracted {stats['total_tables']} tables from {stats['processed']} files",
                metadata=stats
            )
            
        except Exception as e:
            logger.error(f"Extraction failed: {e}")
            return StepResult(
                step_name=self.name,
                status=StepStatus.FAILED,
                error=str(e)
            )


# Backward-compatible function for main.py
def run_extract(
    source_dir: str = None,
    force: bool = False,
    enable_caching: bool = True
):
    """Legacy wrapper for backward compatibility with main.py CLI."""
    from src.pipeline import PipelineStep, PipelineResult
    
    step = ExtractStep(enable_caching=enable_caching, force=force)
    ctx = PipelineContext(source_dir=source_dir)
    result = step.execute(ctx) if step.validate(ctx) else StepResult(
        step_name="extract",
        status=StepStatus.FAILED,
        error="Source directory validation failed"
    )
    
    return PipelineResult(
        step=PipelineStep.EXTRACT,
        success=result.success,
        data=result.data,
        message=result.message,
        error=result.error,
        metadata=result.metadata
    )
