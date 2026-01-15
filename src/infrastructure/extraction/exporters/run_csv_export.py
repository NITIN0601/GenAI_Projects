#!/usr/bin/env python3
"""
Run Excel to CSV Export.

Usage:
    cd /Users/nitin/Desktop/Chatbot/Morgan/GENAI
    python -m src.infrastructure.extraction.exporters.run_csv_export
    
Or:
    python src/infrastructure/extraction/exporters/run_csv_export.py
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from src.infrastructure.extraction.exporters.csv_exporter import get_csv_exporter


def main():
    """Run the CSV export."""
    print("Starting Excel to CSV export...")
    print(f"Project root: {project_root}")
    
    exporter = get_csv_exporter()
    
    print(f"Source directory: {exporter.source_dir}")
    print(f"Output directory: {exporter.output_dir}")
    print()
    
    # Run export
    summary = exporter.export_all()
    
    # Print results
    print("\n" + "=" * 60)
    print("EXPORT SUMMARY")
    print("=" * 60)
    print(f"Workbooks processed: {summary.workbooks_processed}")
    print(f"Total sheets: {summary.total_sheets}")
    print(f"Total tables: {summary.total_tables}")
    print(f"Total CSV files: {summary.total_csv_files}")
    
    if summary.errors:
        print(f"\nErrors ({len(summary.errors)}):")
        for err in summary.errors[:10]:
            print(f"  - {err}")
    else:
        print("\nNo errors!")
    
    print("=" * 60)
    
    return 0 if summary.success else 1


if __name__ == "__main__":
    sys.exit(main())
