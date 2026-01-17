import sys
import os
import logging
from pathlib import Path
import pandas as pd

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logging.getLogger('src.infrastructure.extraction.exporters.table_merger').setLevel(logging.DEBUG)
logger = logging.getLogger(__name__)

from src.pipeline.steps.process_advanced import run_process_advanced
from src.infrastructure.extraction.exporters.table_merger import reset_table_merger

def verify_vertical_merge():
    print("--- Starting Vertical Merge Verification ---")
    
    # Reset singleton to ensure clean state
    reset_table_merger()
    
    # Run the process using the existing source/dest dirs
    # source: data/processed
    # dest: data/processed_advanced
    print("Running process_advanced step...")
    result = run_process_advanced()
    
    if result.success:
        print("✅ Process Advanced step completed successfully.")
        print(f"Stats: {result.data}")
    else:
        print(f"❌ Process Advanced step failed: {result.error}")
        return

    # Check for specific files and their content
    output_dir = Path("data/processed_advanced")
    xlsx_files = list(output_dir.glob("*.xlsx"))
    print(f"Output files: {[f.name for f in xlsx_files]}")

    # Inspect 10q0624_tables.xlsx if it exists (suspected source of 70_1)
    target_file = output_dir / "10q0624_tables.xlsx"
    if target_file.exists():
        print(f"\nInspecting {target_file.name} Index...")
        df = pd.read_excel(target_file, sheet_name='Index')
        
        # Check for 70_1, 70_2
        # If merged vertically, they might still be named 70_1 if 70 was split?
        # WAIT: If vertical merge succeeds, there should be NO split parts if strict matching worked.
        # But if the user's image showed 70_1, 70_2, it meant they WEREN'T merged.
        # If I merged them, they should be just ONE table. 
        # Note: If BlockDetector split them, table_merger re-merges them.
        # If re-merged, we likely keep the first block's naming? 
        # But wait, IndexManager creates names based on sheets.
        # If they are merged, there will be FEWER sheets.
        
        # Let's count occurrences of "Part" or "_"
        split_tables = df[df['Table_ID'].astype(str).str.contains('_', regex=False)]
        print(f"Split tables count: {len(split_tables)}")
        if len(split_tables) > 0:
            print("Found remaining split tables:")
            print(split_tables[['Table_ID', 'Table Title']].head().to_string())
        else:
            print("✅ No split tables found! Vertical merge likely successful.")

if __name__ == "__main__":
    verify_vertical_merge()
