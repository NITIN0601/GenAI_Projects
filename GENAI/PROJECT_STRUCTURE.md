# GENAI Project Structure

**Last Updated**: 2025-12-02  
**Total Python Files**: 224  
**Total Directories**: 35+

---

## 📁 Root Directory

```
/GENAI/
├── main.py                          # Main CLI entry point
├── quickstart.sh                    # Quick setup script
├── run_complete_pipeline.py         # Full pipeline execution
├── test_faiss_metadata.py          # FAISS metadata verification
├── verify_dimension.py             # Embedding dimension checker
├── requirements.txt                # Full dependencies
├── requirements-minimal.txt        # Minimal dependencies
├── README.md                       # Project documentation
├── EXECUTION_GUIDE.md             # Execution instructions
└── PROJECT_STRUCTURE.md           # This file
```

---

## 📂 `/config` - Configuration

```
config/
├── __init__.py
└── settings.py                     # Centralized settings (Pydantic)
```

**Purpose**: Application configuration with environment variable support
- Embedding provider settings (local, custom)
- LLM provider settings (Ollama, custom)
- Vector DB provider settings (ChromaDB, FAISS, Redis)
- Feature flags and paths

---

## 📂 `/scripts` - Utility Scripts

```
scripts/
├── README.md
├── download_documents.py           # SEC filing downloader
├── ingest_pipeline.py             # Data ingestion pipeline
├── migrate_vectordb.py            # Vector DB migration tool
├── verify_imports.py              # Import verification
└── audit_imports.py               # Import auditing
```

**Purpose**: Standalone scripts for data management and system maintenance

---

## 📂 `/src` - Source Code

### `/src/cache` - Caching Layer

```
src/cache/
├── __init__.py
└── backends/
    ├── __init__.py
    └── redis_cache.py              # Redis caching implementation
```

**Purpose**: Query result caching for performance optimization

---

### `/src/embeddings` - Embedding Generation

```
src/embeddings/
├── __init__.py
├── manager.py                      # Unified embedding manager
├── multi_level.py                  # Multi-level embedding generator
├── chunking/
│   ├── __init__.py
│   └── table_chunker.py           # Table-specific chunking
└── providers/
    ├── __init__.py
    ├── base.py                     # Abstract embedding provider
    └── custom_api_provider.py     # Custom API embedding provider
```

**Purpose**: Embedding generation with support for multiple providers
- **Local**: sentence-transformers (FREE)
- **Custom**: Bearer token API integration

**Key Features**:
- Multi-level embeddings (table, row, cell)
- Provider abstraction
- Batch processing

---

### `/src/extraction` - PDF Table Extraction

```
src/extraction/
├── __init__.py
├── base.py                         # Base extraction classes
├── extractor.py                    # Unified extractor orchestrator
├── strategy.py                     # Extraction strategy selection
├── quality.py                      # Quality assessment
├── metrics.py                      # Extraction metrics
├── cache.py                        # Extraction result caching
├── enrichment.py                   # Metadata enrichment
├── backends/                       # Extraction backends
│   ├── __init__.py
│   ├── docling_backend.py         # Docling (primary)
│   ├── pymupdf_backend.py         # PyMuPDF (fallback)
│   ├── pdfplumber_backend.py      # PDFPlumber (fallback)
│   └── camelot_backend.py         # Camelot (fallback)
├── consolidation/                  # Table consolidation
│   ├── __init__.py
│   ├── table_consolidator.py      # Base consolidator
│   ├── quarterly.py               # Quarterly consolidation
│   └── multi_year.py              # Multi-year consolidation
└── formatters/                     # Table formatting
    ├── __init__.py
    ├── table_formatter.py         # Basic table formatting
    ├── enhanced_formatter.py      # Advanced formatting
    └── metadata_extractor.py      # Metadata extraction
```

**Purpose**: Extract tables from financial PDFs with quality assessment
- **Primary**: Docling (best quality)
- **Fallback**: PyMuPDF, PDFPlumber, Camelot
- **Consolidation**: Merge tables across quarters/years
- **Enrichment**: Add financial context (units, currency, etc.)

---

### `/src/llm` - Language Model Management

```
src/llm/
├── __init__.py
├── manager.py                      # Unified LLM manager
└── providers/
    ├── __init__.py
    └── base.py                     # Abstract LLM provider
```

**Purpose**: LLM integration with provider abstraction
- **Ollama**: Local LLM (FREE)
- **Custom**: Bearer token API integration

---

### `/src/models` - Data Models

```
src/models/
├── __init__.py
├── vectordb_schemas.py            # Vector DB specific schemas
└── schemas/
    ├── __init__.py
    ├── schemas.py                 # Core RAG models (27 fields)
    └── enhanced_schemas.py        # Advanced extraction models
```

**Purpose**: Pydantic models for type safety and validation

**Key Models**:
- `TableMetadata` (27 fields): Comprehensive table metadata
  - Core: source_doc, page_no, table_title
  - Temporal: year, quarter, report_type, fiscal_period
  - Structure: column_headers, row_headers, column_count, row_count
  - Multi-level: has_multi_level_headers, main_header, sub_headers
  - Hierarchical: has_hierarchy, subsections, table_structure
  - Financial: units, currency, has_currency, currency_count
  - Embedding: embedding_model, embedded_date
- `TableChunk`: Chunk with content, embedding, metadata
- `SearchResult`: Search result with score
- `RAGQuery`, `RAGResponse`: Query/response models

---

### `/src/prompts` - Prompt Templates

```
src/prompts/
├── __init__.py
├── base.py                         # Base prompts
├── advanced.py                     # Advanced prompts
├── few_shot.py                     # Few-shot examples
└── search_strategies.py            # Search-specific prompts
```

**Purpose**: Centralized prompt management for LLM interactions

---

### `/src/rag` - RAG Pipeline

```
src/rag/
├── __init__.py
├── pipeline.py                     # Query engine (LangChain LCEL)
└── exporter.py                     # Result export (CSV, Excel, JSON)
```

**Purpose**: RAG query processing and result export
- LangChain LCEL pipeline
- Multi-format export
- Source tracking

---

### `/src/retrieval` - Retrieval & Search

```
src/retrieval/
├── __init__.py
├── retriever.py                    # Basic retriever
├── query_processor.py              # Complete query processor
├── query_understanding.py          # Query parsing & classification
├── reranking/
│   ├── __init__.py
│   └── cross_encoder.py           # Cross-encoder reranking
└── search/
    ├── __init__.py
    ├── base.py                     # Search base classes
    ├── factory.py                  # Strategy factory
    ├── orchestrator.py            # Search orchestrator
    ├── fusion/                     # Result fusion
    │   ├── __init__.py
    │   ├── rrf.py                 # Reciprocal Rank Fusion
    │   ├── linear.py              # Linear fusion
    │   └── weighted.py            # Weighted fusion
    └── strategies/                 # Search strategies
        ├── __init__.py
        ├── vector_search.py       # Pure vector search
        ├── keyword_search.py      # BM25 keyword search
        ├── hybrid_search.py       # Hybrid (vector + keyword)
        ├── hyde_search.py         # Hypothetical Document Embeddings
        └── multi_query_search.py  # Multi-query expansion
```

**Purpose**: Advanced retrieval with multiple search strategies
- **Vector Search**: Semantic similarity
- **Keyword Search**: BM25 full-text
- **Hybrid Search**: Best of both worlds
- **HyDE**: Generate hypothetical answers
- **Multi-Query**: Query expansion
- **Reranking**: Cross-encoder reranking
- **Fusion**: Combine multiple strategies

---

### `/src/scheduler` - Automated Filing Scheduler

```
src/scheduler/
├── __init__.py
├── scheduler.py                    # APScheduler integration
└── filing_calendar.py             # SEC filing calendar
```

**Purpose**: Automatic SEC filing monitoring and download
- Predicts filing dates based on historical patterns
- Automatic download on filing release
- Configurable check intervals

---

### `/src/utils` - Utilities

```
src/utils/
├── __init__.py
├── logger.py                       # Centralized logging
├── exceptions.py                   # Custom exceptions
├── helpers.py                      # Helper functions
├── metrics.py                      # Performance metrics
└── extraction_utils.py            # Extraction utilities
```

**Purpose**: Shared utilities and helper functions

---

### `/src/vector_store` - Vector Database

```
src/vector_store/
├── __init__.py
├── manager.py                      # Unified VectorDB manager
├── schemas/
│   ├── __init__.py
│   └── document_schema.py         # Document schemas
└── stores/
    ├── __init__.py
    ├── chromadb_store.py          # ChromaDB implementation
    ├── faiss_store.py             # FAISS implementation
    └── redis_store.py             # Redis implementation
```

**Purpose**: Vector database abstraction layer
- **ChromaDB**: Default, persistent, easy to use
- **FAISS**: High-performance, optimized for speed
- **Redis**: Distributed, production-scale

**Unified Interface**:
- `add_chunks()`: Add embeddings with metadata
- `search()`: Semantic search with filters
- `get_by_metadata()`: Metadata-based retrieval
- `delete_by_source()`: Remove by document
- `get_stats()`: Database statistics

**Switching Providers**:
```python
# In .env or settings.py
VECTORDB_PROVIDER=faiss  # or chromadb, redis
```

---

## 📂 `/tests` - Test Suite

```
tests/
├── README.md
├── unit/                           # Unit tests
│   ├── test_chunking.py
│   ├── test_custom_api.py
│   ├── test_enhanced_formatter.py
│   ├── test_extraction_all.py
│   ├── test_formatter.py
│   ├── test_header_flattening.py
│   ├── test_spanning_headers.py
│   ├── test_table_features.py
│   ├── test_table_structure.py
│   └── test_unified_metadata.py
├── integration/                    # Integration tests
│   ├── test_docling_sample.py
│   ├── test_extraction.py
│   ├── test_real_tables.py
│   └── test_unified_extraction.py
└── system/                         # System tests
    ├── test_query_engine.py
    └── test_system.py
```

**Purpose**: Comprehensive test coverage
- **Unit**: Component-level testing
- **Integration**: Multi-component testing
- **System**: End-to-end testing

---

## 📂 `/archive` - Legacy Code

```
archive/
├── extraction/                     # Old extraction code
├── retrieval/                      # Old retrieval code
└── unwanted/                       # Deprecated code
```

**Purpose**: Archived code for reference (not actively used)

---

## 📂 `/data` - Data Directories

```
data/
├── cache/                          # Cached extraction results
├── processed/                      # Processed data
└── raw/                           # Raw data (alternative location)
```

---

## 📂 `/raw_data` - PDF Storage

```
raw_data/                           # Downloaded PDFs (default location)
```

---

## 📂 `/outputs` - Output Files

```
outputs/
├── consolidated_tables/            # Consolidated table exports
├── exports/                        # RAG query exports
└── old_results/                   # Legacy results
```

---

## 🔑 Key Architecture Patterns

### 1. **Manager Pattern**
- `EmbeddingManager`: Unified embedding interface
- `LLMManager`: Unified LLM interface
- `VectorDBManager`: Unified vector DB interface

### 2. **Provider Pattern**
- Abstract base classes (`EmbeddingProvider`, `LLMProvider`)
- Multiple implementations (local, custom API)
- Easy to add new providers

### 3. **Strategy Pattern**
- `SearchStrategy`: Multiple search algorithms
- `ExtractionStrategy`: Multiple extraction backends
- Runtime selection based on config

### 4. **Factory Pattern**
- `SearchStrategyFactory`: Create search strategies
- `get_*_manager()`: Singleton factories

### 5. **Singleton Pattern**
- Global instances for managers
- Consistent state across application

---

## 📊 Statistics

- **Total Python Files**: ~224
- **Total Lines of Code**: ~22,000+
- **Core Modules**: 12
- **Supported Vector DBs**: 3 (ChromaDB, FAISS, Redis)
- **Supported Embedding Providers**: 2 (Local, Custom API)
- **Supported LLM Providers**: 2 (Ollama, Custom API)
- **Search Strategies**: 5 (Vector, Keyword, Hybrid, HyDE, Multi-Query)
- **Extraction Backends**: 4 (Docling, PyMuPDF, PDFPlumber, Camelot)

---

## 🚀 Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Download PDFs
python main.py download --yr 20-25

# 3. Extract tables and create embeddings
python main.py extract

# 4. Query the system
python main.py query "What was revenue in Q1 2025?"

# 5. Interactive mode
python main.py interactive
```

---

## 🔧 Configuration

All configuration is centralized in `config/settings.py`:

```python
# Embedding Provider
EMBEDDING_PROVIDER = "local"  # or "custom"

# LLM Provider
LLM_PROVIDER = "ollama"  # or "custom"

# Vector DB Provider
VECTORDB_PROVIDER = "faiss"  # or "chromadb", "redis"
```

Switch providers by changing **one setting** - no code changes needed!

---

## 📝 Notes

- All metadata fields (27 total) are stored in vector DB
- Embedding vectors are stored in optimized indices (FAISS, ChromaDB, Redis)
- System is fully provider-agnostic and scalable
- Production-ready with comprehensive error handling and logging
