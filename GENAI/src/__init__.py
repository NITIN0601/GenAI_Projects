"""
GENAI RAG System - Source Package

Enterprise-level RAG system for financial document processing.

Architecture:
- domain/: Core business entities (TableMetadata, RAGQuery, etc.)
- infrastructure/: External integrations (vectordb, embeddings, llm, cache)
- application/: Use cases (query, ingest)
- core/: Shared kernel (paths, exceptions, interfaces)
- rag/: RAG pipeline orchestration
- retrieval/: Query processing and search
- pipeline/: Data processing steps
- evaluation/: Quality metrics
- guardrails/: Safety filters
- prompts/: Prompt templates
- scheduler/: Filing calendar
- utils/: Shared utilities
"""

__version__ = "2.2.0"
__author__ = "GENAI Team"

__all__ = [
    # Core layers
    'core',
    'domain',
    'infrastructure',
    'application',
    # RAG components
    'rag',
    'retrieval',
    'pipeline',
    # Support
    'evaluation',
    'guardrails',
    'prompts',
    'scheduler',
    'utils',
]
