"""
Query Step - RAG query with LLM response.

Implements StepInterface following system architecture pattern.
Uses QueryUseCase for caching support.
"""

from typing import Dict, Any

from src.pipeline.base import StepInterface, StepResult, StepStatus, PipelineContext
from src.utils import get_logger

logger = get_logger(__name__)


class QueryStep(StepInterface):
    """
    RAG query with LLM response generation.
    
    Implements StepInterface (like VectorDBInterface pattern).
    Uses application layer QueryUseCase for caching.
    
    Reads: context.query, context.top_k
    Writes: context.results["query"]
    """
    
    name = "query"
    
    def __init__(self, use_cache: bool = True, force_refresh: bool = False):
        self.use_cache = use_cache
        self.force_refresh = force_refresh
    
    def validate(self, context: PipelineContext) -> bool:
        """Validate query exists."""
        if not context.query:
            logger.error("No query provided for RAG query")
            return False
        return True
    
    def get_step_info(self) -> Dict[str, Any]:
        """Get step metadata."""
        from config.settings import settings
        return {
            "name": self.name,
            "description": "RAG query with LLM response generation",
            "reads": ["context.query", "context.top_k"],
            "writes": ["context.results['query']"],
            "use_cache": self.use_cache,
            "llm_provider": settings.LLM_PROVIDER
        }
    
    def execute(self, context: PipelineContext) -> StepResult:
        """Execute RAG query step."""
        try:
            # Use the application layer QueryUseCase for caching
            from src.application import get_query_use_case
            
            query_uc = get_query_use_case()
            response = query_uc.query(
                query=context.query,
                top_k=context.top_k,
                force_refresh=self.force_refresh or not self.use_cache,
            )
            
            return StepResult(
                step_name=self.name,
                status=StepStatus.SUCCESS,
                data={
                    'answer': response.answer,
                    'sources': response.sources,
                    'confidence': response.confidence,
                    'from_cache': response.from_cache,
                },
                message="Query processed successfully",
                metadata={
                    'question': context.query,
                    'retrieved_chunks': response.retrieved_chunks,
                    'from_cache': response.from_cache,
                }
            )
        except ImportError:
            # Fallback to direct query processor
            try:
                from src.retrieval.query_processor import get_query_processor
                
                processor = get_query_processor()
                result = processor.process_query(context.query)
                
                return StepResult(
                    step_name=self.name,
                    status=StepStatus.SUCCESS,
                    data={'answer': result},
                    message="Query processed successfully",
                    metadata={'question': context.query}
                )
            except ImportError as e:
                return StepResult(
                    step_name=self.name,
                    status=StepStatus.FAILED,
                    error=f"Query processor not available: {e}"
                )
        except Exception as e:
            logger.error(f"Query failed: {e}")
            return StepResult(
                step_name=self.name,
                status=StepStatus.FAILED,
                error=str(e)
            )


# Backward-compatible function for main.py
def run_query(
    question: str,
    top_k: int = 5,
    use_cache: bool = True,
    force_refresh: bool = False,
):
    """Legacy wrapper for backward compatibility with main.py CLI."""
    from src.pipeline import PipelineStep, PipelineResult
    
    step = QueryStep(use_cache=use_cache, force_refresh=force_refresh)
    ctx = PipelineContext(query=question, top_k=top_k)
    result = step.execute(ctx) if step.validate(ctx) else StepResult(
        step_name="query",
        status=StepStatus.FAILED,
        error="No query provided"
    )
    
    return PipelineResult(
        step=PipelineStep.QUERY,
        success=result.success,
        data=result.data,
        message=result.message,
        error=result.error,
        metadata=result.metadata
    )
