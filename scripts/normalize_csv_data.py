"""
Script to normalize CSV files from wide to long format.

Usage:
    python scripts/normalize_csv_data.py [--workbook <workbook_name>] [--all]
    
Examples:
    # Normalize all CSV files for a specific workbook
    python scripts/normalize_csv_data.py --workbook 10q0925
    
    # Normalize all CSV files in all workbooks
    python scripts/normalize_csv_data.py --all
"""

import sys
import argparse
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core import get_paths
from src.utils import get_logger
from src.infrastructure.extraction.exporters.csv_exporter import get_csv_exporter

logger = get_logger(__name__)


def normalize_workbook(workbook_name: str, csv_output_dir: Path) -> bool:
    """
    Normalize all CSV files for a specific workbook.
    
    Args:
        workbook_name: Name of the workbook (e.g., '10q0925')
        csv_output_dir: Base CSV output directory
        
    Returns:
        True if successful, False otherwise
    """
    workbook_dir = csv_output_dir / workbook_name
    
    if not workbook_dir.exists():
        logger.error(f"Workbook directory not found: {workbook_dir}")
        return False
    
    logger.info(f"Normalizing CSV files for workbook: {workbook_name}")
    
    # Find all CSV files (except Index.csv)
    csv_files = [f for f in workbook_dir.glob("*.csv") if f.name != "Index.csv"]
    
    if not csv_files:
        logger.warning(f"No CSV files found in {workbook_dir}")
        return False
    
    logger.info(f"Found {len(csv_files)} CSV files to normalize")
    
    # Create normalizer
    from src.infrastructure.extraction.exporters.csv_exporter.data_normalizer import normalize_csv_file
    
    # Normalize each file
    success_count = 0
    for csv_file in csv_files:
        logger.info(f"Normalizing: {csv_file.name}")
        
        if normalize_csv_file(str(csv_file)):
            success_count += 1
        else:
            logger.error(f"Failed to normalize: {csv_file.name}")
    
    logger.info(f"Normalized {success_count}/{len(csv_files)} files successfully")
    
    return success_count == len(csv_files)


def normalize_all_workbooks(csv_output_dir: Path) -> bool:
    """
    Normalize all CSV files in all workbooks.
    
    Args:
        csv_output_dir: Base CSV output directory
        
    Returns:
        True if all successful, False otherwise
    """
    # Find all workbook directories
    workbook_dirs = [d for d in csv_output_dir.iterdir() if d.is_dir()]
    
    if not workbook_dirs:
        logger.error(f"No workbook directories found in {csv_output_dir}")
        return False
    
    logger.info(f"Found {len(workbook_dirs)} workbooks to process")
    
    # Normalize each workbook
    success_count = 0
    for workbook_dir in workbook_dirs:
        if normalize_workbook(workbook_dir.name, csv_output_dir):
            success_count += 1
    
    logger.info(f"Normalized {success_count}/{len(workbook_dirs)} workbooks successfully")
    
    return success_count == len(workbook_dirs)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Normalize CSV files from wide to long format"
    )
    parser.add_argument(
        "--workbook",
        type=str,
        help="Name of the workbook to normalize (e.g., '10q0925')"
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Normalize all workbooks"
    )
    
    args = parser.parse_args()
    
    # Get paths
    paths = get_paths()
    csv_output_dir = Path(paths.data_dir) / "csv_output"
    
    if not csv_output_dir.exists():
        logger.error(f"CSV output directory not found: {csv_output_dir}")
        return 1
    
    # Determine what to normalize
    if args.all:
        success = normalize_all_workbooks(csv_output_dir)
    elif args.workbook:
        success = normalize_workbook(args.workbook, csv_output_dir)
    else:
        parser.print_help()
        return 1
    
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
