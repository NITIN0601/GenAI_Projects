# Import Guide - GENAI Codebase

## Overview

After the restructuring, all imports now follow a consistent pattern using the `src.` prefix. The `models/` directory has been moved to `src/models/` to eliminate circular dependencies.

## New Import Structure

### Models and Schemas

All data models are now under `src.models`:

```python
# Table schemas
from src.models.schemas import TableMetadata, TableChunk, FinancialTable

# Enhanced schemas
from src.models.enhanced_schemas import (
    EnhancedDocument,
    DocumentMetadata,
    EnhancedFinancialTable,
    ColumnHeader,
    RowHeader,
    DataCell,
    Period
)

# Vector DB schemas
from src.models.vectordb_schemas import TableChunk, VectorDBStats

# Embedding models
from src.models.embeddings import (
    EmbeddingProvider,
    EmbeddingManager,
    get_embedding_manager
)
```

### Extraction System

```python
# Main extractor
from src.extraction import Extractor, extract_pdf

# Backends
from src.extraction.backends import (
    DoclingBackend,
    PyMuPDFBackend,
    PDFPlumberBackend,
    CamelotBackend
)

# Formatters
from src.extraction.formatters.table_formatter import (
    TableStructureFormatter,
    format_table_structure
)

from src.extraction.formatters.enhanced_formatter import (
    EnhancedTableFormatter,
    format_enhanced_table
)

# Quality and caching
from src.extraction.quality import QualityAssessor
from src.extraction.cache import ExtractionCache
from src.extraction.strategy import ExtractionStrategy
```

### Embeddings

```python
# Embedding manager
from src.embeddings.manager import get_embedding_manager

# Multi-level embeddings
from src.embeddings.multi_level import MultiLevelEmbeddingGenerator

# Chunking
from src.embeddings.chunking import TableChunker, get_table_chunker

# Providers
from src.embeddings.providers import (
    OpenAIEmbeddingProvider,
    LocalEmbeddingProvider
)
```

### Vector Store

```python
# Vector store interface
from src.vector_store.stores.chromadb_store import get_vector_store

# Other stores
from src.vector_store.stores.faiss_store import FAISSVectorStore
from src.vector_store.stores.redis_store import RedisVectorStore
```

### RAG System

```python
# Query processing
from src.retrieval.query_processor import get_query_processor, QueryProcessor

# Retriever
from src.retrieval.retriever import get_retriever, Retriever

# RAG pipeline
from src.rag.pipeline import get_query_engine
from src.rag.query_understanding import QueryUnderstanding, QueryType
from src.rag.table_consolidation import TableConsolidationEngine
```

### Utilities

```python
# Logging
from src.utils import get_logger, setup_logging

# Exceptions
from src.utils import (
    GENAIException,
    ExtractionError,
    EmbeddingError,
    VectorStoreError,
    LLMError,
    RAGError
)

# Helper functions
from src.utils import (
    compute_file_hash,
    get_pdf_files,
    ensure_directory,
    format_number,
    truncate_text
)

# Extraction utilities
from src.utils.extraction_utils import (
    PDFMetadataExtractor,
    DoclingHelper,
    TableClassifier
)

# Metrics
from src.utils.metrics import get_metrics_collector
```

### Cache System

```python
# Redis cache
from src.cache.backends.redis_cache import get_redis_cache
```

## Common Import Patterns

### For Scripts

Scripts in the `scripts/` directory should import like this:

```python
#!/usr/bin/env python3
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Now import from src
from src.extraction import Extractor
from src.models.schemas import TableMetadata
from src.embeddings.manager import get_embedding_manager
```

### For Tests

Tests in the `tests/` directory:

```python
import pytest
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Import from src
from src.extraction import Extractor
from src.models.schemas import TableMetadata
```

### For Main Application

The `main.py` file:

```python
from src.extraction.extractor import UnifiedExtractor as Extractor
from src.embeddings.multi_level import MultiLevelEmbeddingGenerator
from src.embeddings.manager import get_embedding_manager
from src.vector_store.stores.chromadb_store import get_vector_store
from src.retrieval.query_processor import get_query_processor
from src.cache.backends.redis_cache import get_redis_cache
from src.models.enhanced_schemas import EnhancedDocument, DocumentMetadata
```

## Module Organization

```
src/
├── models/              # All data models and schemas
│   ├── schemas/         # Basic schemas
│   ├── embeddings/      # Embedding-related models
│   ├── enhanced_schemas.py
│   └── vectordb_schemas.py
├── extraction/          # PDF extraction system
│   ├── backends/        # Different extraction backends
│   ├── formatters/      # Table formatters
│   ├── extractor.py     # Main extractor
│   ├── quality.py       # Quality assessment
│   └── cache.py         # Extraction caching
├── embeddings/          # Embedding generation
│   ├── chunking/        # Text/table chunking
│   ├── providers/       # Embedding providers
│   ├── manager.py       # Embedding manager
│   └── multi_level.py   # Multi-level embeddings
├── vector_store/        # Vector database
│   └── stores/          # Different vector store implementations
├── retrieval/           # Query and retrieval
│   ├── query_processor.py
│   └── retriever.py
├── rag/                 # RAG pipeline
│   ├── pipeline.py
│   ├── query_understanding.py
│   └── table_consolidation.py
├── llm/                 # LLM integration
│   ├── manager.py
│   └── prompts/
├── cache/               # Caching system
│   └── backends/
└── utils/               # Utilities
    ├── logger.py
    ├── exceptions.py
    ├── helpers.py
    ├── extraction_utils.py
    └── metrics.py
```

## Migration from Old Imports

If you have old code using the previous import structure, update as follows:

### Old → New

```python
# OLD (deprecated)
from models.schemas import TableMetadata
from models.enhanced_schemas import EnhancedDocument
from extraction.extractor import UnifiedExtractor

# NEW (correct)
from src.models.schemas import TableMetadata
from src.models.enhanced_schemas import EnhancedDocument
from src.extraction.extractor import UnifiedExtractor
```

## Best Practices

1. **Always use absolute imports** from `src.` - no relative imports
2. **Import specific items** instead of using wildcards (`from module import *`)
3. **Group imports** logically: stdlib, third-party, then src imports
4. **Use type hints** with imported types for better IDE support

## Troubleshooting

### Import Error: "No module named 'models'"

**Problem**: Old import path being used  
**Solution**: Update to `from src.models import ...`

### Import Error: "cannot import name 'X'"

**Problem**: Function or class doesn't exist in module  
**Solution**: Check the module's `__all__` list or view the source file

### Circular Import Error

**Problem**: Two modules importing from each other  
**Solution**: This should not happen with the new structure. If it does, report it as a bug.

## Summary

- All imports now use `src.` prefix
- `models/` is now `src/models/`
- No circular dependencies
- Consistent import patterns throughout
- Better IDE support and type checking
