# Import Guide - GENAI Codebase

## Overview

The GENAI codebase follows a domain-driven design pattern. All core data models are defined in `src/domain/` as the **single source of truth**.

## Import Structure

### Domain Layer (Recommended)

All core schemas are in `src.domain`:

```python
# Table schemas (recommended)
from src.domain.tables import TableMetadata, TableChunk, FinancialTable

# Query/Response schemas
from src.domain.queries import RAGQuery, RAGResponse, SearchResult

# Document schemas
from src.domain.documents import DocumentMetadata, PageLayout, Period, DocumentProcessingResult

# Or import from domain root
from src.domain import TableMetadata, RAGQuery, RAGResponse
```

### Models Layer (Convenience Re-exports)

For convenience, `src.models` re-exports from `src.domain`:

```python
# These work but domain imports are preferred
from src.models import TableMetadata, RAGQuery, RAGResponse
from src.models.schemas import TableMetadata, TableChunk
```

### Enhanced Schemas

Extended schemas not yet migrated to domain:

```python
from src.models.schemas.enhanced_schemas import (
    EnhancedDocument,
    EnhancedFinancialTable,
    ColumnHeader,
    RowHeader,
    DataCell,
)
```

### Infrastructure Layer

```python
# Extraction
from src.infrastructure.extraction.extractor import UnifiedExtractor

# Embeddings
from src.infrastructure.embeddings.manager import get_embedding_manager
from src.infrastructure.embeddings.chunking import TableChunker

# VectorDB
from src.infrastructure.vectordb.manager import get_vectordb_manager
from src.infrastructure.vectordb.stores.faiss_store import FAISSVectorStore
from src.infrastructure.vectordb.stores.chromadb_store import VectorStore
from src.infrastructure.vectordb.stores.redis_store import RedisVectorStore

# LLM
from src.infrastructure.llm.manager import get_llm_manager
```

### RAG and Retrieval

```python
# Query processing
from src.retrieval.query_processor import get_query_processor, QueryProcessor
from src.retrieval.retriever import get_retriever, Retriever

# RAG pipeline
from src.rag.pipeline import get_query_engine
```

### Utilities

```python
# Logging
from src.utils import get_logger, setup_logging

# Cleanup utilities
from src.utils.cleanup import clear_all_cache, full_clean, quick_clean

# Extraction utilities
from src.utils.extraction_utils import PDFMetadataExtractor, DoclingHelper
```

## Module Organization

```
src/
├── domain/              # SINGLE SOURCE OF TRUTH for data models
│   ├── tables/          # TableMetadata, TableChunk, FinancialTable
│   ├── queries/         # RAGQuery, RAGResponse, SearchResult
│   └── documents/       # DocumentMetadata, PageLayout, Period
├── models/              # Re-exports from domain (convenience)
│   └── schemas/         # Re-exports + enhanced_schemas
├── infrastructure/      # External system integrations
│   ├── extraction/      # PDF extraction backends
│   ├── embeddings/      # Embedding generation
│   ├── vectordb/        # Vector database stores
│   ├── llm/             # LLM providers
│   └── cache/           # Caching backends
├── retrieval/           # Query and retrieval
├── rag/                 # RAG pipeline
├── pipeline/            # Data processing pipeline
│   └── steps/           # extract, embed steps
├── core/                # Core utilities and interfaces
└── utils/               # Helper utilities
```

## Factory Methods

### TableMetadata.from_extraction()

Create TableMetadata from extraction results:

```python
from src.domain.tables import TableMetadata

metadata = TableMetadata.from_extraction(
    table_meta=table_data,       # Dict or object with table-level metadata
    doc_metadata=doc_info,       # Dict with document-level metadata
    filename="10q0625.pdf",
    table_index=0,
    embedding=embedding_vector,   # Optional
    embedding_model="all-MiniLM-L6-v2",
    embedding_provider="local"
)
```

## Common Import Patterns

### For Pipeline Steps

```python
from src.domain.tables import TableChunk, TableMetadata
from src.infrastructure.embeddings.manager import get_embedding_manager
from src.infrastructure.vectordb.manager import get_vectordb_manager
```

### For Scripts

```python
#!/usr/bin/env python3
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.domain import TableMetadata, RAGQuery
from src.infrastructure.extraction.extractor import UnifiedExtractor
```

### For Tests

```python
import pytest
from src.domain.tables import TableMetadata, TableChunk
```

## Best Practices

1. **Import from `src.domain`** for core schemas (TableMetadata, RAGQuery, etc.)
2. **Use absolute imports** from `src.` - no relative imports
3. **Import specific items** instead of wildcards
4. **Group imports** logically: stdlib, third-party, then src imports
5. **Use SecretStr** for sensitive fields in Pydantic settings
6. **Use `field(default_factory=list)`** for mutable dataclass defaults

## Singleton Patterns

The codebase uses two singleton patterns depending on metaclass compatibility:

### Option 1: ThreadSafeSingleton Metaclass (Preferred)

Use for classes without metaclass conflicts:

```python
from src.core.singleton import ThreadSafeSingleton

class QueryEngine(metaclass=ThreadSafeSingleton):
    def __init__(self, config=None):
        self.config = config

# Usage
engine1 = QueryEngine(config="prod")
engine2 = QueryEngine()  # Returns same instance
assert engine1 is engine2

# Reset for testing
QueryEngine._reset_instance()
```

### Option 2: SingletonRegistry (For Metaclass Conflicts)

Use when class has conflicting metaclass (e.g., LangChain Embeddings):

```python
from src.core.singleton import get_singleton_registry

_singleton_registry = get_singleton_registry()

class EmbeddingManager:
    def __init__(self, model_name=None):
        self.model_name = model_name

def get_embedding_manager(**kwargs):
    return _singleton_registry.get_or_create(
        EmbeddingManager,
        EmbeddingManager,
        **kwargs
    )

def reset_embedding_manager():
    _singleton_registry.reset(EmbeddingManager)
```

> [!TIP]
> Always provide `reset_*` functions for singleton managers to support testing.

## Migration Reference

```python
# OLD (deprecated)
from src.models.schemas import TableMetadata
from models.schemas import TableMetadata

# NEW (correct)
from src.domain.tables import TableMetadata
from src.domain import TableMetadata
```
