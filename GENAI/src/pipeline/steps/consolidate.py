"""
Consolidate Step - Table consolidation and export.

Implements StepInterface following system architecture pattern.
"""

from typing import Dict, Any, Optional

from src.pipeline.base import StepInterface, StepResult, StepStatus, PipelineContext
from src.utils import get_logger

logger = get_logger(__name__)


class ConsolidateStep(StepInterface):
    """
    Consolidate tables and export as timeseries.
    
    Implements StepInterface (like VectorDBInterface pattern).
    
    Reads: context.query (table_title)
    Writes: Exports consolidated tables to files
    """
    
    name = "consolidate"
    
    def __init__(
        self,
        output_format: str = "both",
        output_dir: Optional[str] = None,
        transpose: bool = True
    ):
        self.output_format = output_format
        self.output_dir = output_dir
        self.transpose = transpose
    
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
            "reads": ["context.query (table_title)"],
            "writes": ["CSV/Excel files"],
            "output_format": self.output_format,
            "transpose": self.transpose
        }
    
    def execute(self, context: PipelineContext) -> StepResult:
        """Execute consolidation step."""
        from config.settings import settings
        
        table_title = context.query
        output_dir = self.output_dir or getattr(settings, 'OUTPUT_DIR', 'outputs/consolidated_tables')
        
        try:
            from src.infrastructure.extraction.consolidation import get_quarterly_consolidator
            from src.infrastructure.embeddings.manager import get_embedding_manager
            from src.infrastructure.vectordb.manager import get_vectordb_manager
            
            vector_store = get_vectordb_manager()
            embedding_manager = get_embedding_manager()
            
            # Initialize consolidator
            consolidator = get_quarterly_consolidator(vector_store, embedding_manager)
            
            # Find matching tables
            tables = consolidator.find_tables_by_title(table_title, top_k=50)
            
            if not tables:
                return StepResult(
                    step_name=self.name,
                    status=StepStatus.FAILED,
                    error=f"No matching tables found for '{table_title}'"
                )
            
            # Consolidate
            df, metadata = consolidator.consolidate_tables(tables, table_name=table_title)
            
            if df.empty:
                return StepResult(
                    step_name=self.name,
                    status=StepStatus.FAILED,
                    error="Failed to consolidate tables"
                )
            
            # Export
            export_paths = consolidator.export(df, table_title, metadata.get('date_range'))
            
            return StepResult(
                step_name=self.name,
                status=StepStatus.SUCCESS,
                data={
                    'dataframe': df,
                    'tables_found': len(tables),
                    'export_paths': export_paths
                },
                message=f"Consolidated {len(tables)} tables, exported to {self.output_format}",
                metadata={
                    'quarters_included': metadata.get('quarters_included', []),
                    'total_rows': metadata.get('total_rows', 0),
                    'total_columns': metadata.get('total_columns', 0)
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
    transpose: bool = True
):
    """Legacy wrapper for backward compatibility with main.py CLI."""
    from src.pipeline import PipelineStep, PipelineResult
    
    step = ConsolidateStep(
        output_format=output_format,
        output_dir=output_dir,
        transpose=transpose
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
