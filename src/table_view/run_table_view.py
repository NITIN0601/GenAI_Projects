"""
Table View Module Runner.

This script orchestrates the generation of the Table Time-Series Views.
It executes the two main components in order:
1. MasterTableIndexGenerator
2. TableViewGenerator
"""

import sys
import argparse
import logging
from pathlib import Path

# Add project root to python path to allow imports if run standalone
project_root = Path(__file__).resolve().parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.table_view.master_table_index_generator import MasterTableIndexGenerator
from src.table_view.table_view_generator import TableViewGenerator

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("TableViewOrchestrator")

def main():
    parser = argparse.ArgumentParser(description="Generate Time-Series Table Views")
    parser.add_argument("--input_file", type=Path, default=Path("data/consolidate/Master_Consolidated.csv"), help="Path to Master_Consolidated.csv")
    parser.add_argument("--output_dir", type=Path, default=Path("data/table_views"), help="Directory to save output")
    
    args = parser.parse_args()
    
    input_file = args.input_file.resolve()
    output_dir = args.output_dir.resolve()
    
    if not input_file.exists():
        logger.error(f"Input file not found: {input_file}")
        sys.exit(1)
        
    logger.info(f"Starting Table View Generation from {input_file}")
    
    # Step 1: Generate Index
    logger.info("\n--- Step 1: Generating Master Table Index ---")
    try:
        index_gen = MasterTableIndexGenerator(input_file, output_dir)
        index_path = index_gen.generate_index()
    except Exception as e:
        logger.error(f"Failed to generate index: {e}")
        sys.exit(1)
        
    # Step 2: Generate Views
    logger.info("\n--- Step 2: Generating Table Views ---")
    try:
        view_gen = TableViewGenerator(input_file, index_path, output_dir)
        view_gen.generate_views()
    except Exception as e:
        logger.error(f"Failed to generate views: {e}")
        sys.exit(1)
        
    logger.info("\nTable View Generation Completed Successfully.")

if __name__ == "__main__":
    main()
