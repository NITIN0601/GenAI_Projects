"""
Application layer - Use cases and orchestration.

Contains high-level use cases that coordinate domain entities
and infrastructure services:
- IngestUseCase: Document ingestion with deduplication and caching
- QueryUseCase: RAG queries with caching and evaluation
"""

from src.application.use_cases import (
    IngestUseCase,
    QueryUseCase,
    get_ingest_use_case,
    get_query_use_case,
)

__all__ = [
    'IngestUseCase',
    'QueryUseCase',
    'get_ingest_use_case',
    'get_query_use_case',
]
