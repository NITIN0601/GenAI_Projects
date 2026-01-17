"""
Orchestrate Full GENAI Pipeline.

This script executes the complete data processing pipeline in a strictly sequential order.
It ensures that each step completes successfully before moving to the next.

Pipeline Steps:
0. Index Sheet Re-sequencing: Cleans xlsx structure and splits multi-table sheets.
1-4. Wide Format Export: Extracts data, injects metadata, formats values, creates formatted CSVs.
5. Normalized Export: Creates long-format CSVs (Dates, Header, Data Value).
6. Merge & Consolidation: Merges normalized CSVs into a master dataset.
7. Table Time-Series View Generation: Generates Master Index and View CSVs.

Usage:
    python3 -m src.pipeline.orchestrate_pipeline
"""

import sys
import subprocess
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("PipelineOrchestrator")


def run_command(command: str, step_name: str, stop_on_failure: bool = True) -> bool:
    """Run a shell command and check for success."""
    logger.info(f"\n{'='*80}")
    logger.info(f"STARTING: {step_name}")
    logger.info(f"COMMAND: {command}")
    logger.info(f"{'='*80}\n")
    
    try:
        # Run command and stream output
        process = subprocess.run(
            command,
            shell=True,
            check=stop_on_failure,
            text=True
        )
        
        if process.returncode == 0:
            logger.info(f"\n✅ COMPLETED: {step_name}\n")
            return True
        else:
            logger.error(f"\n❌ FAILED: {step_name} (Return Code: {process.returncode})\n")
            return False
            
    except subprocess.CalledProcessError as e:
        logger.error(f"\n❌ FAILED: {step_name}\nError: {e}\n")
        if stop_on_failure:
            sys.exit(1)
        return False
    except Exception as e:
        logger.error(f"\n❌ ERROR in {step_name}: {e}\n")
        if stop_on_failure:
            sys.exit(1)
        return False


def main():
    """Execute the full pipeline."""
    base_dir = Path.cwd()
    data_dir = base_dir / "data"
    
    logger.info("Starting GENAI Pipeline Orchestration...")
    logger.info(f"Working Directory: {base_dir}")
    
    # ---------------------------------------------------------
    # Step 0: Index Sheet Re-sequencing
    # ---------------------------------------------------------
    # Updates .xlsx files in data/processed/ in-place
    cmd_step0 = "python3 scripts/test_index_resequencer.py --mode all --dir data/processed"
    run_command(cmd_step0, "Step 0: Index Sheet Re-sequencing")
    
    # ---------------------------------------------------------
    # Steps 1-4: Wide Format Export (Standard)
    # ---------------------------------------------------------
    # Exports to data/csv_output/
    # Features enabled by default: Category Separation, Metadata Injection, Data Formatting
    cmd_step1_4 = "python3 -m src.infrastructure.extraction.exporters.run_csv_export"
    run_command(cmd_step1_4, "Steps 1-4: Wide Format Export (Standard)")
    
    # ---------------------------------------------------------
    # Step 5: Normalized Export (Long Format)
    # ---------------------------------------------------------
    # Exports to data/csv_output_normalized/
    # explicitly enables data normalization flag
    
    # We use a small python script to invoke the exporter because passing complex args 
    # to run_csv_export.py via CLI might be limited if it doesn't expose all flags (it currently doesn't).
    # Building a dynamic python command.
    
    python_script = """
import sys
from pathlib import Path
# Add project root to path
sys.path.insert(0, ".")

from src.infrastructure.extraction.exporters.csv_exporter import get_csv_exporter

print("Starting Normalized Export (Step 5)...")
exporter = get_csv_exporter(
    enable_data_normalization=True,
    output_dir=Path("data/csv_output_normalized")
)
summary = exporter.export_all()
if not summary.success:
    sys.exit(1)
"""
    # Escape quotes for shell
    cmd_step5 = f"python3 -c '{python_script}'"
    run_command(cmd_step5, "Step 5: Normalized Export (Long Format)")
    
    # ---------------------------------------------------------
    # Step 6: Merge & Consolidation
    # ---------------------------------------------------------
    # Consolidates from data/csv_output_normalized/ to data/consolidate/
    cmd_step6 = (
        "python3 -m src.pipeline.merge_csv_pipeline "
        "--base-dir data/csv_output_normalized "
        "--output-dir data/consolidate"
    )
    run_command(cmd_step6, "Step 6: Merge & Consolidation")

    # ---------------------------------------------------------
    # Step 7: Table Time-Series View Generation
    # ---------------------------------------------------------
    # Generates Master_Table_Index.csv and [Table_ID].csv files in data/table_views/
    cmd_step7 = "python3 src/table_view/run_table_view.py"
    run_command(cmd_step7, "Step 7: Table Time-Series View Generation")
    
    logger.info(f"\n{'='*80}")
    logger.info("🎉 PIPELINE EXECUTION COMPLETED SUCCESSFULLY 🎉")
    logger.info(f"{'='*80}\n")


if __name__ == "__main__":
    main()
