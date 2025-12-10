"""
Consolidate Step - Table consolidation and export.

Implements StepInterface following system architecture pattern.
"""

from typing import Dict, Any, Optional, List

from src.pipeline.base import StepInterface, StepResult, StepStatus, PipelineContext
from src.utils import get_logger

logger = get_logger(__name__)


class ConsolidateStep(StepInterface):
    """
    Consolidate tables and export as timeseries.
    
    Implements StepInterface (like VectorDBInterface pattern).
    
    Reads: context.query (table_title), context.filters (optional years/quarters)
    Writes: Exports consolidated tables to files
    """
    
    name = "consolidate"
    
    def __init__(
        self,
        output_format: str = "both",
        output_dir: Optional[str] = None,
        transpose: bool = True,
        years: Optional[List[int]] = None,
        quarters: Optional[List[str]] = None
    ):
        self.output_format = output_format
        self.output_dir = output_dir
        self.transpose = transpose
        self.years = years
        self.quarters = quarters
    
    def validate(self, context: PipelineContext) -> bool:
        """Validate table title is provided."""
        if not context.query:
            logger.error("No table_title (query) provided for consolidation")
            return False
        return True
    
    def get_step_info(self) -> Dict[str, Any]:
        """Get step metadata."""
        return {
            "name": self.name,
            "description": "Consolidate tables across quarters and export",
            "reads": ["context.query (table_title)", "context.filters"],
            "writes": ["CSV/Excel files"],
            "output_format": self.output_format,
            "transpose": self.transpose
        }
    
    def execute(self, context: PipelineContext) -> StepResult:
        """Execute consolidation step."""
        from config.settings import settings
        
        table_title = context.query
        output_dir = self.output_dir or getattr(settings, 'OUTPUT_DIR', 'outputs/consolidated_tables')
        
        # Get year/quarter filters from context or step config
        filters = context.filters or {}
        years = self.years or filters.get('years')
        quarters = self.quarters or filters.get('quarters')
        
        try:
            from src.infrastructure.extraction.consolidation import get_table_consolidator
            
            # Initialize unified consolidator
            consolidator = get_table_consolidator()
            
            # Find matching tables with filters
            tables = consolidator.find_tables(
                title=table_title,
                years=years,
                quarters=quarters,
                top_k=50
            )
            
            if not tables:
                return StepResult(
                    step_name=self.name,
                    status=StepStatus.FAILED,
                    error=f"No matching tables found for '{table_title}'"
                )
            
            # Consolidate
            result = consolidator.consolidate(
                tables,
                table_name=table_title,
                transpose=self.transpose
            )
            
            if result.dataframe.empty:
                return StepResult(
                    step_name=self.name,
                    status=StepStatus.FAILED,
                    error="Failed to consolidate tables"
                )
            
            # Export
            export_paths = consolidator.export(
                result,
                output_dir=output_dir,
                format=self.output_format
            )
            
            return StepResult(
                step_name=self.name,
                status=StepStatus.SUCCESS,
                data={
                    'dataframe': result.dataframe,
                    'tables_found': len(tables),
                    'export_paths': export_paths,
                    'validation': result.validation
                },
                message=f"Consolidated {len(tables)} tables, exported to {self.output_format}",
                metadata={
                    'periods_included': result.periods_included,
                    'years': result.years,
                    'quarters': result.quarters,
                    'total_rows': result.total_rows,
                    'total_columns': result.total_columns
                }
            )
        except ImportError as e:
            return StepResult(
                step_name=self.name,
                status=StepStatus.FAILED,
                error=f"Consolidator not available: {e}"
            )
        except Exception as e:
            logger.error(f"Consolidation failed: {e}")
            return StepResult(
                step_name=self.name,
                status=StepStatus.FAILED,
                error=str(e)
            )


# Backward-compatible function for main.py
def run_consolidate(
    table_title: str,
    output_format: str = "both",
    output_dir: Optional[str] = None,
    transpose: bool = True,
    years: Optional[List[int]] = None,
    quarters: Optional[List[str]] = None
):
    """
    Legacy wrapper for backward compatibility with main.py CLI.
    
    Args:
        table_title: Title of table to consolidate
        output_format: "csv", "excel", or "both"
        output_dir: Output directory
        transpose: If True, dates become rows
        years: Optional list of years to filter
        quarters: Optional list of quarters to filter
    """
    from src.pipeline import PipelineStep, PipelineResult
    
    step = ConsolidateStep(
        output_format=output_format,
        output_dir=output_dir,
        transpose=transpose,
        years=years,
        quarters=quarters
    )
    ctx = PipelineContext(query=table_title)
    result = step.execute(ctx) if step.validate(ctx) else StepResult(
        step_name="consolidate",
        status=StepStatus.FAILED,
        error="No table title provided"
    )
    
    return PipelineResult(
        step=PipelineStep.CONSOLIDATE,
        success=result.success,
        data=result.data,
        message=result.message,
        error=result.error,
        metadata=result.metadata
    )
