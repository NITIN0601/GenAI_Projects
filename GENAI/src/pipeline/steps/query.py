"""
Query Step - RAG query with LLM response.

Uses QueryUseCase for caching support.
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


def run_query(
    question: str,
    top_k: int = 5,
    use_cache: bool = True,
    force_refresh: bool = False,
):
    """
    Step 7: Query with LLM response.
    
    Args:
        question: User question
        top_k: Number of context chunks
        use_cache: Whether to use query cache
        force_refresh: Force fresh results (skip cache)
        
    Returns:
        PipelineResult with LLM response
    """
    from src.pipeline import PipelineStep, PipelineResult
    
    try:
        # Use the application layer QueryUseCase for caching
        from src.application import get_query_use_case
        
        query_uc = get_query_use_case()
        response = query_uc.query(
            query=question,
            top_k=top_k,
            force_refresh=force_refresh or not use_cache,
        )
        
        return PipelineResult(
            step=PipelineStep.QUERY,
            success=True,
            data={
                'answer': response.answer,
                'sources': response.sources,
                'confidence': response.confidence,
                'from_cache': response.from_cache,
            },
            message="Query processed successfully",
            metadata={
                'question': question,
                'retrieved_chunks': response.retrieved_chunks,
                'from_cache': response.from_cache,
            }
        )
    except ImportError:
        # Fallback to direct query processor
        try:
            from src.retrieval.query_processor import get_query_processor
            
            processor = get_query_processor()
            result = processor.process_query(question)
            
            return PipelineResult(
                step=PipelineStep.QUERY,
                success=True,
                data={'answer': result},
                message="Query processed successfully",
                metadata={'question': question}
            )
        except ImportError as e:
            return PipelineResult(
                step=PipelineStep.QUERY,
                success=False,
                error=f"Query processor not available: {e}"
            )
    except Exception as e:
        logger.error(f"Query failed: {e}")
        return PipelineResult(
            step=PipelineStep.QUERY,
            success=False,
            error=str(e)
        )
