"""
Application use cases.

High-level orchestration of domain entities and infrastructure services.
"""

from src.application.use_cases.ingest import IngestUseCase, get_ingest_use_case
from src.application.use_cases.query import QueryUseCase, get_query_use_case

__all__ = [
    'IngestUseCase',
    'QueryUseCase',
    'get_ingest_use_case',
    'get_query_use_case',
]
