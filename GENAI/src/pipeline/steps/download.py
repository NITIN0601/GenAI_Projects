"""
Download Step - PDF document download with retry logic.

Implements StepInterface following system architecture pattern.
"""

from typing import Dict, Any, Optional
from pathlib import Path

from src.pipeline.base import StepInterface, StepResult, StepStatus, PipelineContext
from src.utils import get_logger

logger = get_logger(__name__)


class DownloadStep(StepInterface):
    """
    Download PDF files from configured sources.
    
    Implements StepInterface (like VectorDBInterface pattern).
    
    Reads: context settings
    Writes: Downloads files to output directory
    """
    
    name = "download"
    
    def __init__(
        self,
        year_range: str = "25",
        month: Optional[str] = None,
        timeout: int = 30,
        max_retries: int = 3
    ):
        self.year_range = year_range
        self.month = month
        self.timeout = timeout
        self.max_retries = max_retries
    
    def validate(self, context: PipelineContext) -> bool:
        """Validate download is enabled."""
        from config.settings import settings
        
        if hasattr(settings, 'DOWNLOAD_ENABLED') and not settings.DOWNLOAD_ENABLED:
            logger.error("Download disabled in settings (DOWNLOAD_ENABLED=False)")
            return False
        return True
    
    def get_step_info(self) -> Dict[str, Any]:
        """Get step metadata."""
        return {
            "name": self.name,
            "description": "Download PDF files from configured source",
            "reads": ["settings.DOWNLOAD_BASE_URL"],
            "writes": ["files to RAW_DATA_DIR"],
            "timeout": self.timeout,
            "max_retries": self.max_retries
        }
    
    def execute(self, context: PipelineContext) -> StepResult:
        """Execute download step."""
        from config.settings import settings
        
        output_dir = context.source_dir or settings.RAW_DATA_DIR
        
        try:
            from scripts.download_documents import download_files, get_file_names_to_download
            
            base_url = settings.DOWNLOAD_BASE_URL
            file_urls = get_file_names_to_download(base_url, self.month, self.year_range)
            
            results = download_files(
                file_urls=file_urls,
                download_dir=output_dir,
                timeout=self.timeout,
                max_retries=self.max_retries
            )
            
            return StepResult(
                step_name=self.name,
                status=StepStatus.SUCCESS,
                data=results['successful'],
                message=f"Downloaded {len(results['successful'])} files",
                metadata={
                    'failed': results['failed'],
                    'output_dir': output_dir
                }
            )
        except Exception as e:
            logger.error(f"Download failed: {e}")
            return StepResult(
                step_name=self.name,
                status=StepStatus.FAILED,
                error=str(e)
            )


# Backward-compatible function for main.py
def run_download(
    year_range: str,
    month: Optional[str] = None,
    output_dir: Optional[str] = None,
    timeout: int = 30,
    max_retries: int = 3
):
    """Legacy wrapper for backward compatibility with main.py CLI."""
    from src.pipeline import PipelineStep, PipelineResult
    
    step = DownloadStep(
        year_range=year_range,
        month=month,
        timeout=timeout,
        max_retries=max_retries
    )
    
    ctx = PipelineContext(source_dir=output_dir)
    result = step.execute(ctx) if step.validate(ctx) else StepResult(
        step_name="download",
        status=StepStatus.FAILED,
        error="Download disabled in settings"
    )
    
    return PipelineResult(
        step=PipelineStep.DOWNLOAD,
        success=result.success,
        data=result.data,
        message=result.message,
        error=result.error,
        metadata=result.metadata
    )
