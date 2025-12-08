"""
Automatic filing download scheduler using APScheduler.

Monitors filing calendar and automatically downloads new filings when they become available.
"""

from datetime import datetime, timedelta
import logging
from src.utils import get_logger
from typing import Optional
from pathlib import Path

try:
    from apscheduler.schedulers.background import BackgroundScheduler
    from apscheduler.triggers.date import DateTrigger
    from apscheduler.triggers.interval import IntervalTrigger
    SCHEDULER_AVAILABLE = True
except ImportError:
    SCHEDULER_AVAILABLE = False

from src.scheduler.filing_calendar import FilingCalendar
from config.settings import settings

logger = get_logger(__name__)


class FilingScheduler:
    """
    Automatic scheduler for SEC filing downloads.
    
    Features:
    - Predicts filing dates based on historical patterns
    - Schedules download jobs automatically
    - Retries for 5 days if filing not available
    - Auto-triggers extraction after download
    - Can run in background or foreground
    """
    
    def __init__(self, auto_extract: bool = True):
        """
        Initialize scheduler.
        
        Args:
            auto_extract: Automatically run extraction after download
        """
        if not SCHEDULER_AVAILABLE:
            raise ImportError(
                "APScheduler not installed. Run: pip install APScheduler>=3.10.0"
            )
        
        self.calendar = FilingCalendar()
        self.scheduler = BackgroundScheduler()
        self.auto_extract = auto_extract
        self.scheduled_jobs = {}
        
        logger.info("Filing Scheduler initialized")
    
    def schedule_upcoming_filings(self, days_ahead: int = 180):
        """
        Schedule download jobs for upcoming filings.
        
        Args:
            days_ahead: Look ahead window in days
        """
        upcoming = self.calendar.get_upcoming_filings(days_ahead=days_ahead)
        
        if not upcoming:
            logger.info(f"No upcoming filings in next {days_ahead} days")
            return
        
        logger.info(f"Scheduling {len(upcoming)} upcoming filings")
        
        for filing in upcoming:
            self._schedule_filing_download(filing)
    
    def _schedule_filing_download(self, filing: dict):
        """Schedule download job for a specific filing with retry logic."""
        # Schedule multiple attempts over 5-day window
        retry_days = 5
        
        for retry_day in range(retry_days):
            run_date = filing["predicted_date"] + timedelta(days=retry_day)
            
            # Skip if date is in the past
            if run_date < datetime.now():
                continue
            
            job_id = f"filing_{filing['report_year']}_{filing['quarter']}_retry{retry_day}"
            
            try:
                self.scheduler.add_job(
                    func=self._download_filing,
                    trigger=DateTrigger(run_date=run_date),
                    args=[filing],
                    id=job_id,
                    replace_existing=True,
                    name=f"{filing['filing_name']} (Attempt {retry_day + 1})"
                )
                
                self.scheduled_jobs[job_id] = {
                    "filing": filing,
                    "run_date": run_date,
                    "retry": retry_day
                }
                
                logger.info(
                    f"Scheduled: {filing['filing_name']} - "
                    f"{run_date.strftime('%Y-%m-%d')} (Attempt {retry_day + 1})"
                )
                
            except Exception as e:
                logger.error(f"Failed to schedule job {job_id}: {e}")
    
    def _download_filing(self, filing: dict):
        """
        Download a specific filing.
        
        Args:
            filing: Filing info dictionary from calendar
        """
        logger.info(f"Attempting to download: {filing['filing_name']}")
        
        try:
            # Import here to avoid circular imports
            from scripts.download_documents import download_files, get_file_names_to_download
            
            # Get download URLs
            base_url = settings.DOWNLOAD_BASE_URL
            
            file_urls = get_file_names_to_download(
                base_url=base_url,
                m=filing["month_code"],
                yr=filing["year_code"]
            )
            
            if not file_urls:
                logger.warning(f"No files found for {filing['filing_name']}")
                return False
            
            # Download files
            logger.info(f"Found {len(file_urls)} files to download")
            
            results = download_files(
                file_urls=file_urls,
                download_dir=settings.RAW_DATA_DIR,
                timeout=30,
                max_retries=3
            )
            
            # Check success
            if results['successful']:
                logger.info(
                    f"Downloaded {len(results['successful'])} files for {filing['filing_name']}"
                )
                
                # Trigger extraction if enabled
                if self.auto_extract:
                    self._trigger_extraction()
                
                # Cancel remaining retry jobs for this filing
                self._cancel_retry_jobs(filing)
                
                return True
            else:
                logger.warning(f"Download failed for {filing['filing_name']}")
                return False
                
        except Exception as e:
            logger.error(f"Error downloading {filing['filing_name']}: {e}", exc_info=True)
            return False
    
    def _trigger_extraction(self):
        """Trigger extraction pipeline after successful download."""
        logger.info("Triggering automatic extraction...")
        
        try:
            # Import here to avoid circular imports
            from src.infrastructure.extraction.extractor import UnifiedExtractor
            from pathlib import Path
            
            # Get PDF files from raw_data directory
            raw_data_dir = Path(settings.RAW_DATA_DIR)
            pdf_files = list(raw_data_dir.glob("*.pdf"))
            
            if not pdf_files:
                logger.warning("No PDF files found for extraction")
                return
            
            logger.info(f"Extracting {len(pdf_files)} PDF files...")
            
            # Run extraction (simplified - in production, use full pipeline)
            extractor = UnifiedExtractor(enable_caching=True)
            
            for pdf_file in pdf_files:
                try:
                    result = extractor.extract(str(pdf_file))
                    if result.is_successful():
                        logger.info(f"Extracted {len(result.tables)} tables from {pdf_file.name}")
                    else:
                        logger.warning(f"Extraction failed for {pdf_file.name}: {result.error}")
                except Exception as e:
                    logger.error(f"Error extracting {pdf_file.name}: {e}")
            
            logger.info("Automatic extraction complete")
            
        except Exception as e:
            logger.error(f"Extraction pipeline failed: {e}", exc_info=True)
    
    def _cancel_retry_jobs(self, filing: dict):
        """Cancel remaining retry jobs for a filing after successful download."""
        filing_prefix = f"filing_{filing['report_year']}_{filing['quarter']}"
        
        jobs_to_remove = [
            job_id for job_id in self.scheduled_jobs.keys()
            if job_id.startswith(filing_prefix)
        ]
        
        for job_id in jobs_to_remove:
            try:
                self.scheduler.remove_job(job_id)
                del self.scheduled_jobs[job_id]
                logger.info(f"Cancelled retry job: {job_id}")
            except Exception as e:
                logger.debug(f"Could not remove job {job_id}: {e}")
    
    def add_manual_check(self, interval_hours: int = 24):
        """
        Add periodic manual check job.
        
        Args:
            interval_hours: Check interval in hours
        """
        self.scheduler.add_job(
            func=self._periodic_check,
            trigger=IntervalTrigger(hours=interval_hours),
            id="periodic_check",
            replace_existing=True,
            name=f"Periodic Check (every {interval_hours}h)"
        )
        
        logger.info(f"Added periodic check (every {interval_hours} hours)")
    
    def _periodic_check(self):
        """Periodic check for new filings in current window."""
        logger.info("Running periodic filing check...")
        
        # Check if we're in any filing window
        today = datetime.now()
        
        for quarter in ["Q1", "Q2", "Q3", "10K"]:
            if self.calendar.is_filing_window(quarter, today):
                logger.info(f"Currently in {quarter} filing window")
                
                # Try to download
                # Note: This is a simplified approach
                # In production, you'd want more sophisticated logic
                break
    
    def start(self, daemon: bool = False):
        """
        Start the scheduler.
        
        Args:
            daemon: Run in daemon mode (blocking)
        """
        if not self.scheduler.running:
            self.scheduler.start()
            logger.info("Scheduler started")
            
            # Print scheduled jobs
            jobs = self.scheduler.get_jobs()
            logger.info(f"Active jobs: {len(jobs)}")
            for job in jobs[:5]:  # Show first 5
                logger.info(f"  - {job.name}: {job.next_run_time}")
            
            if daemon:
                logger.info("Running in daemon mode (press Ctrl+C to exit)")
                try:
                    # Keep the scheduler running
                    import time
                    while True:
                        time.sleep(60)
                except (KeyboardInterrupt, SystemExit):
                    logger.info("Shutting down scheduler...")
                    self.stop()
        else:
            logger.warning("Scheduler already running")
    
    def stop(self):
        """Stop the scheduler."""
        if self.scheduler.running:
            self.scheduler.shutdown()
            logger.info("Scheduler stopped")
    
    def get_status(self) -> dict:
        """Get scheduler status and upcoming jobs."""
        jobs = self.scheduler.get_jobs()
        
        return {
            "running": self.scheduler.running,
            "total_jobs": len(jobs),
            "upcoming_jobs": [
                {
                    "name": job.name,
                    "next_run": job.next_run_time,
                    "id": job.id
                }
                for job in sorted(jobs, key=lambda j: j.next_run_time or datetime.max)[:10]
            ]
        }


# Global scheduler instance
_scheduler: Optional[FilingScheduler] = None

def get_scheduler() -> FilingScheduler:
    """Get global scheduler instance."""
    global _scheduler
    if _scheduler is None:
        _scheduler = FilingScheduler()
    return _scheduler
