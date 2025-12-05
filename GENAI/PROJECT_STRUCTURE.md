# GENAI Project Structure

**Last Updated**: 2025-12-05  
**Total Python Files**: 130  
**Total Directories**: 22+

---

## 📁 Root Directory

```
/GENAI/
├── main.py                          # Main CLI entry point (modular)
├── quickstart.sh                    # Quick setup script
├── run_complete_pipeline.py         # Full pipeline execution
├── test_faiss_metadata.py          # FAISS metadata verification
├── test_local_config.py            # Local config testing
├── verify_dimension.py             # Embedding dimension checker
├── verify_consolidation.py         # Table consolidation checker
├── verify_table_id.py              # Table ID verification
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
├── settings.py                     # Centralized settings (Pydantic)
└── prompts.yaml                    # Centralized prompt templates
```

**Purpose**: Application configuration with environment variable support
- Embedding provider settings (local, custom)
- LLM provider settings (Ollama, custom)
- Vector DB provider settings (ChromaDB, FAISS, Redis)
- Feature flags and paths
- **NEW**: Centralized prompt templates and few-shot examples in YAML

**Key Files**:
- `settings.py`: Pydantic-based configuration management
- `prompts.yaml`: All LLM prompt templates (Financial Analysis, CoT, ReAct, HyDE, Multi-Query, Few-Shot examples)

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

**Files**:
- `redis_cache.py`: Redis-based query result caching for performance

**Purpose**: Query result caching for performance optimization

---

### `/src/evaluation` - RAG Evaluation (NEW)

```
src/evaluation/
├── __init__.py
├── base.py                         # BaseEvaluator, EvaluationScores
├── manager.py                      # EvaluationManager (provider switching)
├── heuristic_provider.py           # Fast heuristic evaluation
├── ragas_provider.py               # RAGAS integration (optional)
├── retrieval_metrics.py            # Retrieval quality metrics
├── generation_metrics.py           # Generation quality metrics
├── faithfulness.py                 # Hallucination detection
└── evaluator.py                    # Legacy RAGEvaluator
```

**Files**:
- `base.py`: Abstract base for providers, EvaluationScores with table display
- `manager.py`: Unified manager with heuristic/RAGAS/hybrid switching
- `heuristic_provider.py`: Fast evaluation without LLM (default)
- `ragas_provider.py`: Industry-standard RAGAS integration (optional)
- `retrieval_metrics.py`: Context relevance, Precision@K, MRR
- `generation_metrics.py`: Answer relevance, completeness, conciseness
- `faithfulness.py`: Hallucination detection, claim verification
- `evaluator.py`: RAGEvaluator orchestrating all metrics (legacy)

**Purpose**: Modular RAG pipeline evaluation
- **Heuristic**: Fast, no LLM (default)
- **RAGAS**: Industry-standard, LLM-based
- **Hybrid**: Both for comprehensive assessment

---

### `/src/guardrails` - Safety Guardrails (NEW)

```
src/guardrails/
├── __init__.py
├── input_guard.py                  # Input validation & sanitization
├── output_guard.py                 # Output validation & disclaimers
└── financial_validator.py          # Financial accuracy checks
```

**Files**:
- `input_guard.py`: Prompt injection detection, query classification, filter extraction
- `output_guard.py`: Response validation, disclaimers, sensitive data filtering
- `financial_validator.py`: Number verification, calculation checks, currency formatting

**Purpose**: Safety and accuracy guardrails
- **Input**: Validation, injection detection, off-topic filtering
- **Output**: Disclaimers, formatting, sensitive data filtering
- **Financial**: Number accuracy, calculation verification

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

**Files**:
- `manager.py`: Unified interface for all embedding providers
- `multi_level.py`: Generates embeddings at table, row, and cell levels
- `chunking/table_chunker.py`: Intelligent table chunking for large tables
- `providers/base.py`: Abstract base class for embedding providers
- `providers/custom_api_provider.py`: Custom API integration with bearer token auth

**Purpose**: Embedding generation with support for multiple providers
- **Local**: sentence-transformers (FREE)
- **Custom**: Bearer token API integration

**Key Features**:
- Multi-level embeddings (table, row, cell)
- Provider abstraction
- Batch processing
- Configurable chunk sizes

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

**Files**:
- `base.py`: Base classes for extraction backends (ExtractionBackend, ExtractionResult)
- `extractor.py`: Main orchestrator with multi-backend fallback
- `strategy.py`: Backend selection strategy based on quality
- `quality.py`: Table quality scoring and assessment
- `metrics.py`: Extraction performance metrics
- `cache.py`: File-based caching for extraction results
- `enrichment.py`: Financial metadata enrichment (units, currency, statement types)
- `backends/docling_backend.py`: Primary extraction using Docling
- `backends/pymupdf_backend.py`: Fallback using PyMuPDF
- `backends/pdfplumber_backend.py`: Fallback using PDFPlumber
- `backends/camelot_backend.py`: Fallback using Camelot
- `consolidation/table_consolidator.py`: Base consolidation logic
- `consolidation/quarterly.py`: Quarterly table consolidation
- `consolidation/multi_year.py`: Multi-year table consolidation
- `formatters/table_formatter.py`: Basic markdown table formatting
- `formatters/enhanced_formatter.py`: Advanced formatting with multi-level headers
- `formatters/metadata_extractor.py`: Extract metadata from table content

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
    └── base.py                     # LLM provider implementations
```

**Files**:
- `manager.py`: Unified interface for all LLM providers, supports LangChain integration
- `providers/base.py`: OpenAI and Ollama LLM providers with abstract base class

**Purpose**: LLM integration with provider abstraction
- **Ollama**: Local LLM (FREE)
- **OpenAI**: GPT-3.5-turbo, GPT-4
- **Custom**: Bearer token API integration
- **LangChain**: Full LCEL pipeline support

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

**Files**:
- `vectordb_schemas.py`: Vector database-specific document schemas
- `schemas/schemas.py`: Core Pydantic models (TableMetadata with 27 fields, TableChunk, SearchResult, RAGQuery, RAGResponse)
- `schemas/enhanced_schemas.py`: Enhanced extraction models for advanced processing

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
├── loader.py                       # Prompt loader (Singleton)
├── templates.py                    # Consolidated prompt templates
├── base.py                         # Base prompts (uses loader)
├── advanced.py                     # Advanced prompts (uses loader)
├── few_shot.py                     # Few-shot examples (uses loader)
└── search_strategies.py            # Search-specific prompts (uses loader)
```

**Files**:
- `loader.py`: **NEW** - Singleton PromptLoader class that loads all prompts from `config/prompts.yaml`
- `base.py`: Financial analysis prompts (FINANCIAL_ANALYSIS_PROMPT, FINANCIAL_CHAT_PROMPT, TABLE_COMPARISON_PROMPT, METADATA_EXTRACTION_PROMPT, CITATION_PROMPT)
- `advanced.py`: Advanced reasoning prompts (COT_PROMPT, REACT_PROMPT)
- `few_shot.py`: Few-shot learning manager with semantic similarity example selection (FINANCIAL_EXAMPLES, FewShotManager)
- `search_strategies.py`: Retrieval strategy prompts (HYDE_PROMPT, MULTI_QUERY_PROMPT)

**Purpose**: Centralized prompt management using YAML configuration and Singleton loader

**Key Features**:
- All prompts defined in `config/prompts.yaml`
- Singleton loader ensures single load
- Backward compatible with existing code
- Easy to update prompts without code changes
- Supports LangChain PromptTemplate and ChatPromptTemplate

---

### `/src/rag` - RAG Pipeline

```
src/rag/
├── __init__.py
├── pipeline.py                     # Query engine (LangChain LCEL)
└── exporter.py                     # Result export (CSV, Excel, JSON)
```

**Files**:
- `pipeline.py`: Main RAG query engine using LangChain LCEL chains
- `exporter.py`: Export query results to CSV, Excel, and JSON formats

**Purpose**: RAG query processing and result export
- LangChain LCEL pipeline
- Multi-format export (CSV, Excel, JSON)
- Source tracking and citation
- Multiple prompt strategies (standard, few-shot, CoT, ReAct)

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

**Files**:
- `retriever.py`: Basic retrieval interface
- `query_processor.py`: Complete query processing with consolidation support
- `query_understanding.py`: Query type classification (7 types) and entity extraction
- `reranking/cross_encoder.py`: Cross-encoder reranking for improved relevance
- `search/base.py`: Base classes for search strategies (BaseSearchStrategy, SearchResult)
- `search/factory.py`: Factory for creating search strategies
- `search/orchestrator.py`: Orchestrates multiple search strategies
- `search/fusion/rrf.py`: Reciprocal Rank Fusion algorithm
- `search/fusion/linear.py`: Linear combination fusion
- `search/fusion/weighted.py`: Weighted score fusion
- `search/strategies/vector_search.py`: Pure semantic vector search
- `search/strategies/keyword_search.py`: BM25 keyword search
- `search/strategies/hybrid_search.py`: Hybrid vector + keyword search
- `search/strategies/hyde_search.py`: HyDE (Hypothetical Document Embeddings)
- `search/strategies/multi_query_search.py`: Multi-query expansion

**Purpose**: Advanced retrieval with multiple search strategies
- **Vector Search**: Semantic similarity
- **Keyword Search**: BM25 full-text
- **Hybrid Search**: Best of both worlds
- **HyDE**: Generate hypothetical answers
- **Multi-Query**: Query expansion
- **Reranking**: Cross-encoder reranking
- **Fusion**: Combine multiple strategies (RRF, Linear, Weighted)

**Query Types Supported**:
1. Specific Value
2. Comparison
3. Trend Analysis
4. Aggregation
5. Multi-Document
6. Cross-Table
7. Hierarchical

---

### `/src/scheduler` - Automated Filing Scheduler

```
src/scheduler/
├── __init__.py
├── scheduler.py                    # APScheduler integration
└── filing_calendar.py             # SEC filing calendar
```

**Files**:
- `scheduler.py`: APScheduler-based automated task scheduling
- `filing_calendar.py`: SEC filing calendar with prediction logic

**Purpose**: Automatic SEC filing monitoring and download
- Predicts filing dates based on historical patterns
- Automatic download on filing release
- Configurable check intervals
- Holiday awareness

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

**Files**:
- `logger.py`: Centralized logging configuration with file and console handlers
- `exceptions.py`: Custom exception classes for the application
- `helpers.py`: General helper functions
- `metrics.py`: Performance metrics collection and reporting
- `extraction_utils.py`: Utilities for table extraction and processing

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

**Files**:
- `manager.py`: Unified interface for all vector database providers
- `schemas/document_schema.py`: Document schema definitions
- `stores/chromadb_store.py`: ChromaDB implementation with persistence
- `stores/faiss_store.py`: FAISS implementation with metadata filtering
- `stores/redis_store.py`: Redis implementation for distributed deployments

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
├── test_prompt_loader.py          # NEW - Prompt loader tests
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
- **NEW**: Prompt loader validation tests

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
- **NEW**: `PromptLoader`: Unified prompt management

### 2. **Provider Pattern**
- Abstract base classes (`EmbeddingProvider`, `LLMProvider`)
- Multiple implementations (local, custom API, OpenAI, Ollama)
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
- **NEW**: PromptLoader for single YAML load

### 6. **Configuration-Driven Design**
- All prompts in YAML (enterprise standard)
- Settings in Pydantic models
- Environment variable support

---

## 📊 Statistics

- **Total Python Files**: 122
- **Total Lines of Code**: ~28,000+
- **Core Modules**: 13
- **Supported Vector DBs**: 3 (ChromaDB, FAISS, Redis)
- **Supported Embedding Providers**: 2 (Local, Custom API)
- **Supported LLM Providers**: 3 (Ollama, OpenAI, Custom API)
- **Search Strategies**: 5 (Vector, Keyword, Hybrid, HyDE, Multi-Query)
- **Extraction Backends**: 4 (Docling, PyMuPDF, PDFPlumber, Camelot)
- **Prompts**: 10+ templates (all in YAML)

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
LLM_PROVIDER = "ollama"  # or "openai", "custom"

# Vector DB Provider
VECTORDB_PROVIDER = "faiss"  # or "chromadb", "redis"
```

Switch providers by changing **one setting** - no code changes needed!

**NEW**: Prompts are configured in `config/prompts.yaml` - edit prompts without touching code!

---

## 📝 Recent Updates (2025-12-03)

### Prompt Template Restructuring
- **Added** `config/prompts.yaml`: All prompt templates in YAML
- **Added** `src/prompts/loader.py`: Singleton prompt loader
- **Refactored** all prompt modules to use YAML-based configuration
- **Improved** modularity and enterprise compliance
- **Enhanced** maintainability - update prompts without code changes

### Benefits
- ✅ Configuration-driven architecture
- ✅ No hardcoded prompts in Python files
- ✅ Easy to version control and review prompt changes
- ✅ Supports RAG and future agentic systems
- ✅ Production-ready for November 2025 deployment

---

## 📝 Notes

- All metadata fields (27 total) are stored in vector DB
- Embedding vectors are stored in optimized indices (FAISS, ChromaDB, Redis)
- System is fully provider-agnostic and scalable
- Production-ready with comprehensive error handling and logging
- Prompts are now centralized and configuration-driven (enterprise standard)
