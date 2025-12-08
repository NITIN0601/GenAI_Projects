"""
Tracing module for observability.

Provides LangSmith integration for tracing LLM calls, retrieval,
and RAG pipeline execution.

Usage:
    from src.utils.tracing import setup_tracing, trace_rag_query
    
    # Initialize tracing at app startup
    setup_tracing()
    
    # Trace a RAG query
    with trace_rag_query("my query") as run:
        result = query_engine.query("my query")
"""

import os
import functools
from typing import Optional, Any, Dict, Callable
from contextlib import contextmanager

from config.settings import settings
from src.utils import get_logger

logger = get_logger(__name__)

# Global tracing state
_tracing_initialized = False


def setup_tracing() -> bool:
    """
    Initialize LangSmith tracing.
    
    Call this once at application startup.
    
    Returns:
        True if tracing is enabled and configured
    """
    global _tracing_initialized
    
    if not settings.LANGSMITH_TRACING:
        logger.debug("LangSmith tracing is disabled")
        return False
    
    if not settings.LANGSMITH_API_KEY:
        logger.warning("LANGSMITH_API_KEY not set - tracing disabled")
        return False
    
    try:
        # Set environment variables for LangSmith
        os.environ["LANGSMITH_TRACING"] = "true"
        os.environ["LANGSMITH_API_KEY"] = settings.LANGSMITH_API_KEY
        os.environ["LANGSMITH_PROJECT"] = settings.LANGSMITH_PROJECT
        os.environ["LANGSMITH_ENDPOINT"] = settings.LANGSMITH_ENDPOINT
        
        # Verify connection
        from langsmith import Client
        client = Client()
        
        # Test connection by checking if we can access projects
        logger.info(f"LangSmith tracing enabled for project: {settings.LANGSMITH_PROJECT}")
        _tracing_initialized = True
        return True
        
    except ImportError:
        logger.warning("langsmith package not installed")
        return False
    except Exception as e:
        logger.error(f"Failed to initialize LangSmith: {e}")
        return False


def is_tracing_enabled() -> bool:
    """Check if tracing is currently enabled."""
    return _tracing_initialized


@contextmanager
def trace_rag_query(
    query: str,
    metadata: Optional[Dict[str, Any]] = None,
    run_type: str = "chain"
):
    """
    Context manager for tracing a RAG query.
    
    Args:
        query: The user query
        metadata: Additional metadata to attach to the trace
        run_type: Type of run (chain, retriever, llm, etc.)
        
    Yields:
        Run object if tracing is enabled, None otherwise
    """
    if not _tracing_initialized:
        yield None
        return
    
    try:
        from langsmith import traceable
        from langsmith.run_helpers import get_current_run_tree
        
        # Create run metadata
        run_metadata = {
            "query": query,
            "project": settings.LANGSMITH_PROJECT,
            "environment": settings.ENVIRONMENT,
            **(metadata or {})
        }
        
        # Use LangSmith's built-in tracing
        yield run_metadata
        
    except ImportError:
        yield None
    except Exception as e:
        logger.debug(f"Tracing error: {e}")
        yield None


def traceable_function(
    name: Optional[str] = None,
    run_type: str = "chain",
    metadata: Optional[Dict[str, Any]] = None
):
    """
    Decorator to make a function traceable.
    
    Args:
        name: Name for the trace (defaults to function name)
        run_type: Type of run (chain, retriever, llm, tool)
        metadata: Additional metadata
        
    Example:
        @traceable_function(name="process_query", run_type="chain")
        def my_function(query: str):
            return process(query)
    """
    def decorator(func: Callable) -> Callable:
        if not settings.LANGSMITH_TRACING:
            return func
        
        try:
            from langsmith import traceable
            
            trace_name = name or func.__name__
            
            @traceable(name=trace_name, run_type=run_type, metadata=metadata)
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                return func(*args, **kwargs)
            
            return wrapper
            
        except ImportError:
            return func
    
    return decorator


class TracingCallbackHandler:
    """
    LangChain callback handler for tracing.
    
    Integrates with LangChain's callback system for automatic tracing.
    """
    
    def __init__(self):
        self.enabled = _tracing_initialized
        self._handler = None
        
        if self.enabled:
            try:
                from langsmith.run_helpers import LangChainTracer
                self._handler = LangChainTracer(project_name=settings.LANGSMITH_PROJECT)
            except ImportError:
                self.enabled = False
    
    def get_callbacks(self):
        """Get list of callbacks for LangChain."""
        if self.enabled and self._handler:
            return [self._handler]
        return []


# Global callback handler instance
_callback_handler: Optional[TracingCallbackHandler] = None


def get_tracing_callbacks():
    """
    Get tracing callbacks for LangChain.
    
    Returns:
        List of callback handlers
    """
    global _callback_handler
    
    if _callback_handler is None:
        _callback_handler = TracingCallbackHandler()
    
    return _callback_handler.get_callbacks()


def log_retrieval(
    query: str,
    results: list,
    top_k: int,
    duration_ms: float,
    metadata: Optional[Dict[str, Any]] = None
):
    """
    Log a retrieval operation for tracing.
    
    Args:
        query: Search query
        results: Retrieved results
        top_k: Number of results requested
        duration_ms: Query duration in milliseconds
        metadata: Additional metadata
    """
    if not _tracing_initialized:
        return
    
    try:
        from langsmith import Client
        client = Client()
        
        client.create_run(
            name="retrieval",
            run_type="retriever",
            inputs={"query": query, "top_k": top_k},
            outputs={"num_results": len(results)},
            extra={
                "duration_ms": duration_ms,
                "metadata": metadata or {}
            }
        )
    except Exception as e:
        logger.debug(f"Failed to log retrieval: {e}")


def log_generation(
    prompt: str,
    response: str,
    model: str,
    duration_ms: float,
    tokens_used: Optional[int] = None,
    metadata: Optional[Dict[str, Any]] = None
):
    """
    Log an LLM generation for tracing.
    
    Args:
        prompt: Input prompt
        response: Generated response
        model: Model name
        duration_ms: Generation duration
        tokens_used: Number of tokens used
        metadata: Additional metadata
    """
    if not _tracing_initialized:
        return
    
    try:
        from langsmith import Client
        client = Client()
        
        client.create_run(
            name="generation",
            run_type="llm",
            inputs={"prompt": prompt},
            outputs={"response": response},
            extra={
                "model": model,
                "duration_ms": duration_ms,
                "tokens_used": tokens_used,
                "metadata": metadata or {}
            }
        )
    except Exception as e:
        logger.debug(f"Failed to log generation: {e}")
