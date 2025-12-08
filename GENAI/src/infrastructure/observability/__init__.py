"""
Infrastructure Observability Module.

Provides tracing and monitoring for the RAG system using LangSmith.

Usage:
    from src.infrastructure.observability import setup_tracing, get_tracing_callbacks
    
    # Initialize at app startup
    setup_tracing()
    
    # Get callbacks for LangChain
    callbacks = get_tracing_callbacks()
"""

from src.infrastructure.observability.tracing import (
    setup_tracing,
    is_tracing_enabled,
    trace_rag_query,
    traceable_function,
    get_tracing_callbacks,
    log_retrieval,
    log_generation,
    TracingCallbackHandler,
)

__all__ = [
    'setup_tracing',
    'is_tracing_enabled',
    'trace_rag_query',
    'traceable_function',
    'get_tracing_callbacks',
    'log_retrieval',
    'log_generation',
    'TracingCallbackHandler',
]
