"""
Search Step - Vector search and DB inspection.

Implements StepInterface following system architecture pattern.
"""

from typing import Dict, Any, Optional

from src.pipeline.base import StepInterface, StepResult, StepStatus, PipelineContext
from src.utils import get_logger

logger = get_logger(__name__)


class SearchStep(StepInterface):
    """
    Perform vector similarity search (without LLM).
    
    Implements StepInterface (like VectorDBInterface pattern).
    
    Reads: context.query, context.top_k, context.filters
    Writes: context.results["search"]
    """
    
    name = "search"
    
    def validate(self, context: PipelineContext) -> bool:
        """Validate query exists."""
        if not context.query:
            logger.error("No query provided for search")
            return False
        return True
    
    def get_step_info(self) -> Dict[str, Any]:
        """Get step metadata."""
        from config.settings import settings
        return {
            "name": self.name,
            "description": "Vector similarity search without LLM",
            "reads": ["context.query", "context.top_k", "context.filters"],
            "writes": ["context.results['search']"],
            "vectordb_provider": settings.VECTORDB_PROVIDER
        }
    
    def execute(self, context: PipelineContext) -> StepResult:
        """Execute search step."""
        from config.settings import settings
        from src.infrastructure.vectordb.manager import get_vectordb_manager
        
        try:
            vector_store = get_vectordb_manager()
            vectordb_provider = settings.VECTORDB_PROVIDER
            
            results = vector_store.search(
                query=context.query,
                top_k=context.top_k,
                filters=context.filters
            )
            
            formatted_results = []
            for r in results:
                formatted_results.append({
                    'chunk_id': r.chunk_id,
                    'content': r.content,
                    'score': r.score,
                    'metadata': {
                        'title': r.metadata.table_title if r.metadata else 'N/A',
                        'year': r.metadata.year if r.metadata else 'N/A',
                        'quarter': r.metadata.quarter if r.metadata else 'N/A',
                        'source': r.metadata.source_doc if r.metadata else 'N/A',
                        'page': r.metadata.page_no if r.metadata else 'N/A'
                    }
                })
            
            return StepResult(
                step_name=self.name,
                status=StepStatus.SUCCESS,
                data=formatted_results,
                message=f"Found {len(results)} results for '{context.query}' in {vectordb_provider.upper()}",
                metadata={'query': context.query, 'top_k': context.top_k, 'provider': vectordb_provider}
            )
        except Exception as e:
            logger.error(f"Search failed: {e}")
            return StepResult(
                step_name=self.name,
                status=StepStatus.FAILED,
                error=str(e)
            )


class ViewDBStep(StepInterface):
    """
    View VectorDB contents and schema.
    
    Implements StepInterface.
    """
    
    name = "view_db"
    
    def __init__(self, show_sample: bool = True, sample_count: int = 5):
        self.show_sample = show_sample
        self.sample_count = sample_count
    
    def validate(self, context: PipelineContext) -> bool:
        """Always valid - just viewing DB."""
        return True
    
    def get_step_info(self) -> Dict[str, Any]:
        """Get step metadata."""
        from config.settings import settings
        return {
            "name": self.name,
            "description": "View VectorDB contents and statistics",
            "reads": ["VectorDB"],
            "writes": ["context.results['view_db']"],
            "vectordb_provider": settings.VECTORDB_PROVIDER
        }
    
    def execute(self, context: PipelineContext) -> StepResult:
        """Execute view DB step."""
        from config.settings import settings
        from src.infrastructure.vectordb.manager import get_vectordb_manager
        
        try:
            vector_store = get_vectordb_manager()
            stats = vector_store.get_stats()
            vectordb_provider = stats.get('provider', settings.VECTORDB_PROVIDER)
            
            # Get sample entries
            samples = []
            if self.show_sample:
                try:
                    results = vector_store.search(query="financial", top_k=self.sample_count)
                    for r in results:
                        samples.append({
                            'chunk_id': r.chunk_id,
                            'table_id': r.metadata.table_id if r.metadata and hasattr(r.metadata, 'table_id') else 'N/A',
                            'title': r.metadata.table_title if r.metadata else 'N/A',
                            'year': r.metadata.year if r.metadata else 'N/A',
                            'quarter': r.metadata.quarter if r.metadata else 'N/A',
                            'source': r.metadata.source_doc if r.metadata else 'N/A',
                            'content_preview': r.content[:100] + '...' if len(r.content) > 100 else r.content
                        })
                except Exception:
                    pass
            
            # Get unique documents and titles
            unique_docs = set()
            unique_titles = set()
            years = set()
            quarters = set()
            
            try:
                all_results = vector_store.search(query="", top_k=1000)
                for r in all_results:
                    if r.metadata:
                        if r.metadata.source_doc:
                            unique_docs.add(r.metadata.source_doc)
                        if r.metadata.table_title:
                            unique_titles.add(r.metadata.table_title)
                        if r.metadata.year:
                            years.add(r.metadata.year)
                        if r.metadata.quarter:
                            quarters.add(r.metadata.quarter)
            except Exception:
                pass
            
            db_info = {
                'provider': vectordb_provider,
                'total_chunks': stats.get('total_chunks', 0),
                'unique_documents': len(unique_docs),
                'unique_tables': len(unique_titles),
                'years': sorted(years) if years else [],
                'quarters': sorted(quarters) if quarters else [],
                'table_titles': sorted(list(unique_titles))[:20],
                'samples': samples
            }
            
            return StepResult(
                step_name=self.name,
                status=StepStatus.SUCCESS,
                data=db_info,
                message=f"{vectordb_provider.upper()} DB: {db_info['total_chunks']} chunks, {db_info['unique_documents']} docs",
                metadata=stats
            )
        except Exception as e:
            logger.error(f"View DB failed: {e}")
            return StepResult(
                step_name=self.name,
                status=StepStatus.FAILED,
                error=str(e)
            )


# Backward-compatible functions for main.py
def run_search(
    query: str,
    top_k: int = 5,
    filters: Optional[Dict[str, Any]] = None
):
    """Legacy wrapper for backward compatibility with main.py CLI."""
    from src.pipeline import PipelineStep, PipelineResult
    
    step = SearchStep()
    ctx = PipelineContext(query=query, top_k=top_k, filters=filters)
    result = step.execute(ctx) if step.validate(ctx) else StepResult(
        step_name="search",
        status=StepStatus.FAILED,
        error="No query provided"
    )
    
    return PipelineResult(
        step=PipelineStep.SEARCH,
        success=result.success,
        data=result.data,
        message=result.message,
        error=result.error,
        metadata=result.metadata
    )


def run_view_db(
    show_sample: bool = True,
    sample_count: int = 5
):
    """Legacy wrapper for backward compatibility with main.py CLI."""
    from src.pipeline import PipelineStep, PipelineResult
    
    step = ViewDBStep(show_sample=show_sample, sample_count=sample_count)
    ctx = PipelineContext()
    result = step.execute(ctx)
    
    return PipelineResult(
        step=PipelineStep.VIEW_DB,
        success=result.success,
        data=result.data,
        message=result.message,
        error=result.error,
        metadata=result.metadata
    )
