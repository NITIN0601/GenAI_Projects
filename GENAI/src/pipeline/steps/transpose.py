"""
Transpose Step - Convert consolidated tables to time-series format.

Step 5 in pipeline: Extract → Process → Process-Advanced → Consolidate → Transpose

Implements operations per docs/pipeline_operations.md:
- Multi-sheet processing
- Column header detection (Y/Q)
- Column → Row pivot
- Chronological ordering
- Index/TOC generation
"""

from pathlib import Path
from typing import Dict, Any, Optional

from src.pipeline.base import StepInterface, StepResult, StepStatus, PipelineContext
from src.pipeline import PipelineResult, PipelineStep
from src.utils import get_logger

logger = get_logger(__name__)


class TransposeStep(StepInterface):
    """
    Transpose step - convert consolidated tables to time-series format.
    
    Implements StepInterface following pipeline pattern.
    
    Reads: data/consolidate/consolidated_tables.xlsx
    Writes: data/transpose/consolidated_tables_transposed.xlsx
    """
    
    name = "transpose"
    
    def __init__(self, source_file: Optional[str] = None, output_file: Optional[str] = None):
        """
        Initialize step with optional file overrides.
        
        Args:
            source_file: Override source file path
            output_file: Override output file path
        """
        self.source_file = source_file
        self.output_file = output_file
    
    def validate(self, context: PipelineContext) -> bool:
        """Validate that source file exists."""
        from src.core import get_paths
        
        if self.source_file:
            source_path = Path(self.source_file)
        else:
            paths = get_paths()
            source_path = Path(paths.data_dir) / "consolidate" / "consolidated_tables.xlsx"
        
        if not source_path.exists():
            logger.warning(f"Source file does not exist: {source_path}")
            return False
        
        return True
    
    def get_step_info(self) -> Dict[str, Any]:
        """Get step metadata."""
        return {
            "name": self.name,
            "description": "Convert consolidated tables to time-series format",
            "reads": ["data/consolidate/consolidated_tables.xlsx"],
            "writes": ["data/transpose/consolidated_tables_transposed.xlsx"],
            "operations": [
                "Multi-sheet processing",
                "Y/Q column detection",
                "Column → Row pivot",
                "Chronological ordering"
            ]
        }
    
    def execute(self, context: PipelineContext) -> StepResult:
        """Execute transpose step."""
        import pandas as pd
        from openpyxl import load_workbook
        from src.core import get_paths
        from src.infrastructure.extraction.consolidation.consolidated_exporter_transpose import (
            create_transposed_dataframe,
            reconstruct_metadata_from_df
        )
        
        paths = get_paths()
        
        if self.source_file:
            source_path = Path(self.source_file)
        else:
            source_path = Path(paths.data_dir) / "consolidate" / "consolidated_tables.xlsx"
        
        if self.output_file:
            output_path = Path(self.output_file)
        else:
            output_path = Path(paths.data_dir) / "transpose" / "consolidated_tables_transposed.xlsx"
        
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        stats = {
            'sheets_processed': 0,
            'sheets_skipped': 0,
            'errors': []
        }
        
        try:
            # Load source workbook
            source_wb = load_workbook(source_path)
            sheet_names = source_wb.sheetnames
            source_wb.close()
            
            # Process each sheet
            with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
                for sheet_name in sheet_names:
                    # Skip navigation sheets
                    if sheet_name in ['Index', 'TOC', 'TOC_Sheet']:
                        stats['sheets_skipped'] += 1
                        continue
                    
                    try:
                        self._process_sheet(source_path, sheet_name, writer, stats)
                        stats['sheets_processed'] += 1
                    except Exception as e:
                        logger.warning(f"Error processing sheet {sheet_name}: {e}")
                        stats['errors'].append(f"{sheet_name}: {str(e)}")
                
                # Create Index sheet for transposed output
                self._create_index_sheet(writer, stats['sheets_processed'])
            
            logger.info(f"Transposed {stats['sheets_processed']} sheets to {output_path}")
            
            return StepResult(
                step_name=self.name,
                status=StepStatus.SUCCESS,
                data={
                    'output_path': str(output_path),
                    **stats
                },
                message=f"Transposed {stats['sheets_processed']} sheets",
                metadata={
                    'source': str(source_path),
                    'output': str(output_path)
                }
            )
            
        except Exception as e:
            logger.error(f"Transpose failed: {e}", exc_info=True)
            return StepResult(
                step_name=self.name,
                status=StepStatus.FAILED,
                error=str(e)
            )
    
    def _process_sheet(self, source_path: Path, sheet_name: str, writer, stats: Dict):
        """Process and transpose a single sheet."""
        import pandas as pd
        from src.infrastructure.extraction.consolidation.consolidated_exporter_transpose import (
            create_transposed_dataframe,
            reconstruct_metadata_from_df
        )
        
        # Read the sheet
        df = pd.read_excel(source_path, sheet_name=sheet_name)
        
        # Check for Row Label column (may be named differently)
        first_col = df.columns[0] if len(df.columns) > 0 else None
        if first_col is None:
            logger.warning(f"Sheet {sheet_name} has no columns, skipping")
            return
        
        # If first column isn't 'Row Label', rename it
        if first_col != 'Row Label' and 'Row Label' not in df.columns:
            df = df.rename(columns={first_col: 'Row Label'})
        
        if 'Row Label' not in df.columns:
            logger.warning(f"Sheet {sheet_name} has no Row Label column, skipping")
            return
        
        # Reconstruct metadata for transpose
        row_labels, label_to_section, normalized_row_labels = reconstruct_metadata_from_df(df)
        
        # Transpose
        transposed_df = create_transposed_dataframe(
            df, row_labels, label_to_section, normalized_row_labels
        )
        
        # Write to output
        transposed_df.to_excel(writer, sheet_name=sheet_name, index=False)
    
    def _create_index_sheet(self, writer, total_sheets: int):
        """Create a simple index sheet for the transposed output."""
        import pandas as pd
        
        index_data = {
            'Info': ['Transposed Tables Report'],
            'Value': [f'{total_sheets} sheets processed']
        }
        index_df = pd.DataFrame(index_data)
        index_df.to_excel(writer, sheet_name='Index', index=False)


# Backward-compatible function for main.py CLI
def run_transpose(
    source_file: Optional[str] = None,
    output_file: Optional[str] = None
) -> PipelineResult:
    """
    Run transpose on consolidated tables.
    
    Legacy wrapper maintaining backward compatibility with main.py CLI.
    
    Args:
        source_file: Override source file (default: data/consolidate/consolidated_tables.xlsx)
        output_file: Override output file (default: data/transpose/consolidated_tables_transposed.xlsx)
        
    Returns:
        PipelineResult with processing outcome
    """
    step = TransposeStep(source_file=source_file, output_file=output_file)
    ctx = PipelineContext()
    
    # Validate
    if not step.validate(ctx):
        logger.warning("Validation failed - source file not found")
        return PipelineResult(
            step=PipelineStep.TRANSPOSE if hasattr(PipelineStep, 'TRANSPOSE') else PipelineStep.CONSOLIDATE,
            success=False,
            data={},
            message="Source file not found - run consolidate first",
            error="Validation failed: consolidated_tables.xlsx not found",
            metadata={}
        )
    
    result = step.execute(ctx)
    
    return PipelineResult(
        step=PipelineStep.TRANSPOSE if hasattr(PipelineStep, 'TRANSPOSE') else PipelineStep.CONSOLIDATE,
        success=result.success,
        data=result.data,
        message=result.message,
        error=result.error,
        metadata=result.metadata
    )
