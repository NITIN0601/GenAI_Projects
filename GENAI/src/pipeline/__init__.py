"""
Pipeline Module - Modular Pipeline Steps.

This module provides the core pipeline functions that can be called
programmatically or via CLI commands.

Steps:
1. download - Download files from source
2. extract - Extract tables from PDFs
3. cache - Store extracted data in cache
4. embed - Generate embeddings and store in FAISS
5. view_db - View FAISS DB schema and contents
6. search - Perform search on FAISS
7. query - Send to LLM with prompt
8. consolidate - Get consolidated table by title
9. export - Export as timeseries CSV/Excel
"""

from .steps import (
    PipelineStep,
    run_download,
    run_extract,
    run_embed,
    run_view_db,
    run_search,
    run_query,
    run_consolidate,
)

__all__ = [
    'PipelineStep',
    'run_download',
    'run_extract',
    'run_embed',
    'run_view_db',
    'run_search',
    'run_query',
    'run_consolidate',
]
