"""
Script to export Excel files to CSV with data normalization enabled.

This re-exports the processed Excel files with the data normalization feature
(wide to long format transformation).

Usage:
    python scripts/export_with_normalization.py
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core import get_paths
from src.utils import get_logger
from src.infrastructure.extraction.exporters.csv_exporter import get_csv_exporter

logger = get_logger(__name__)


def main():
    """Export Excel files to CSV with normalization enabled."""
    logger.info("="*80)
    logger.info("Starting Excel to CSV Export with Data Normalization")
    logger.info("="*80)
    
    # Get paths
    paths = get_paths()
    source_dir = Path(paths.data_dir) / "processed"
    output_dir = Path(paths.data_dir) / "csv_output_normalized"
    
    logger.info(f"Source directory: {source_dir}")
    logger.info(f"Output directory: {output_dir}")
    
    # Create exporter with normalization ENABLED
    exporter = get_csv_exporter(
        source_dir=source_dir,
        output_dir=output_dir,
        enable_category_separation=True,
        enable_data_formatting=True,
        enable_metadata_injection=True,
        enable_data_normalization=True  # ← ENABLED
    )
    
    # Export all workbooks
    summary = exporter.export_all()
    
    # Print summary
    logger.info("="*80)
    logger.info("Export Summary")
    logger.info("="*80)
    logger.info(f"Workbooks processed: {summary.workbooks_processed}")
    logger.info(f"Total sheets: {summary.total_sheets}")
    logger.info(f"Total tables: {summary.total_tables}")
    logger.info(f"Total CSV files: {summary.total_csv_files}")
    
    if summary.errors:
        logger.warning(f"Errors encountered: {len(summary.errors)}")
        for error in summary.errors:
            logger.error(f"  - {error}")
    
    if summary.success:
        logger.info("✅ Export completed successfully")
        return 0
    else:
        logger.error("❌ Export failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
