"""
Consolidate Step - Table consolidation and export.
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


def run_consolidate(
    table_title: str,
    output_format: str = "both",
    output_dir: Optional[str] = None,
    transpose: bool = True
):
    """
    Steps 8-9: Consolidate tables and export as timeseries.
    
    Args:
        table_title: Table title to search for
        output_format: Export format ("csv", "excel", or "both")
        output_dir: Output directory
        transpose: Transpose to timeseries format
        
    Returns:
        PipelineResult with consolidated data and export paths
    """
    from src.pipeline import PipelineStep, PipelineResult
    from config.settings import settings
    
    try:
        from src.infrastructure.extraction.consolidation import get_quarterly_consolidator
        from src.infrastructure.embeddings.manager import get_embedding_manager
        from src.infrastructure.vectordb.manager import get_vectordb_manager
        
        vector_store = get_vectordb_manager()
        embedding_manager = get_embedding_manager()
        
        if output_dir is None:
            output_dir = getattr(settings, 'OUTPUT_DIR', 'outputs/consolidated_tables')
        
        # Initialize consolidator
        consolidator = get_quarterly_consolidator(vector_store, embedding_manager)
        
        # Find matching tables
        tables = consolidator.find_tables_by_title(table_title, top_k=50)
        
        if not tables:
            return PipelineResult(
                step=PipelineStep.CONSOLIDATE,
                success=False,
                error=f"No matching tables found for '{table_title}'"
            )
        
        # Consolidate
        df, metadata = consolidator.consolidate_tables(tables, table_name=table_title)
        
        if df.empty:
            return PipelineResult(
                step=PipelineStep.CONSOLIDATE,
                success=False,
                error="Failed to consolidate tables"
            )
        
        # Export
        export_paths = consolidator.export(df, table_title, metadata.get('date_range'))
        
        return PipelineResult(
            step=PipelineStep.CONSOLIDATE,
            success=True,
            data={
                'dataframe': df,
                'tables_found': len(tables),
                'export_paths': export_paths
            },
            message=f"Consolidated {len(tables)} tables, exported to {output_format}",
            metadata={
                'quarters_included': metadata.get('quarters_included', []),
                'total_rows': metadata.get('total_rows', 0),
                'total_columns': metadata.get('total_columns', 0)
            }
        )
    except ImportError as e:
        return PipelineResult(
            step=PipelineStep.CONSOLIDATE,
            success=False,
            error=f"Consolidator not available: {e}"
        )
    except Exception as e:
        logger.error(f"Consolidation failed: {e}")
        return PipelineResult(
            step=PipelineStep.CONSOLIDATE,
            success=False,
            error=str(e)
        )
