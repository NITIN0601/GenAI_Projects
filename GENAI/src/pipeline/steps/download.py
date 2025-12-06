"""
Download Step - PDF document download with retry logic.
"""

import logging
from typing import Optional
from pathlib import Path

logger = logging.getLogger(__name__)


def run_download(
    year_range: str,
    month: Optional[str] = None,
    output_dir: Optional[str] = None,
    timeout: int = 30,
    max_retries: int = 3
):
    """
    Step 1: Download PDF files.
    
    Args:
        year_range: Year or range (e.g., "25" or "20-25")
        month: Optional month filter (03, 06, 09, 12)
        output_dir: Output directory
        timeout: Download timeout per file
        max_retries: Max retry attempts
        
    Returns:
        PipelineResult with downloaded file paths
    """
    from src.pipeline import PipelineStep, PipelineResult
    from config.settings import settings
    
    # Check if download is enabled
    if hasattr(settings, 'DOWNLOAD_ENABLED') and not settings.DOWNLOAD_ENABLED:
        return PipelineResult(
            step=PipelineStep.DOWNLOAD,
            success=False,
            message="Download disabled in settings (DOWNLOAD_ENABLED=False)",
            error="Download disabled"
        )
    
    if output_dir is None:
        output_dir = settings.RAW_DATA_DIR
    
    try:
        from scripts.download_documents import download_files, get_file_names_to_download
        
        base_url = settings.DOWNLOAD_BASE_URL
        file_urls = get_file_names_to_download(base_url, month, year_range)
        
        results = download_files(
            file_urls=file_urls,
            download_dir=output_dir,
            timeout=timeout,
            max_retries=max_retries
        )
        
        return PipelineResult(
            step=PipelineStep.DOWNLOAD,
            success=True,
            data=results['successful'],
            message=f"Downloaded {len(results['successful'])} files",
            metadata={
                'failed': results['failed'],
                'output_dir': output_dir
            }
        )
    except Exception as e:
        logger.error(f"Download failed: {e}")
        return PipelineResult(
            step=PipelineStep.DOWNLOAD,
            success=False,
            error=str(e)
        )
