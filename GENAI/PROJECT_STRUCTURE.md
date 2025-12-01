# Financial RAG System - Project Structure

> **Morgan Stanley 10-Q/10-K Financial Document Analysis System**  
> LangChain-orchestrated RAG pipeline with advanced hybrid search capabilities

---

## 📁 Project Structure

```
GENAI/
├── 📄 main.py                          # Main CLI entry point
├── 📄 requirements.txt                 # Python dependencies
├── 📄 .env.example                     # Configuration template
├── 📄 README.md                        # Project overview
│
├── 📂 config/                          # Configuration & Settings
│   ├── settings.py                     # Centralized settings (VectorDB, LLM, Embeddings)
│   ├── prompts.py                      # LangChain prompt templates
│   └── __init__.py
│
├── 📂 src/                             # Core Application Code
│   ├── 📂 extraction/                  # PDF Extraction System
│   │   ├── extractor.py                # Unified extractor with fallback
│   │   ├── enrichment.py               # ✨ Metadata enrichment (NEW)
│   │   ├── base.py                     # Base classes & interfaces
│   │   ├── strategy.py                 # Extraction strategy
│   │   ├── quality.py                  # Quality assessment
│   │   ├── cache.py                    # Extraction caching
│   │   ├── 📂 backends/                # Extraction backends
│   │   │   ├── docling_backend.py      # Docling (primary)
│   │   │   ├── pymupdf_backend.py      # PyMuPDF (fallback)
│   │   │   ├── pdfplumber_backend.py   # PDFPlumber (fallback)
│   │   │   └── camelot_backend.py      # Camelot (fallback)
│   │   └── 📂 formatters/              # Output formatters
│   │
│   ├── 📂 embeddings/                  # Embedding Generation
│   │   ├── manager.py                  # Embedding manager (unified interface)
│   │   ├── multi_level.py              # Multi-level embeddings
│   │   ├── 📂 chunking/                # Table chunking
│   │   │   └── table_chunker.py        # Smart table chunker
│   │   └── 📂 providers/               # Embedding providers
│   │       ├── local_provider.py       # HuggingFace (FREE)
│   │       ├── openai_provider.py      # OpenAI (PAID)
│   │       └── custom_api_provider.py  # Custom API
│   │
│   ├── 📂 vector_store/                # Vector Database Layer
│   │   └── 📂 stores/
│   │       ├── faiss_store.py          # FAISS (LangChain-compliant)
│   │       ├── chromadb_store.py       # ChromaDB (LangChain-compliant)
│   │       └── redis_store.py          # Redis (LangChain-compliant)
│   │
│   ├── 📂 retrieval/                   # Retrieval & Search
│   │   ├── retrievers.py               # ✨ Advanced retrievers (NEW)
│   │   │                               #    - BM25Retriever
│   │   │                               #    - EnsembleRetriever (Hybrid)
│   │   ├── retriever.py                # Base retriever
│   │   ├── query_processor.py          # Query processing pipeline
│   │   ├── query_classifier.py         # Query type classification
│   │   ├── query_parser.py             # Query parsing
│   │   └── reranker.py                 # Result reranking
│   │
│   ├── 📂 llm/                         # LLM Integration
│   │   ├── manager.py                  # LLM manager
│   │   └── 📂 providers/
│   │       ├── ollama_provider.py      # Ollama (FREE)
│   │       ├── openai_provider.py      # OpenAI (PAID)
│   │       └── custom_api_provider.py  # Custom API
│   │
│   ├── 📂 rag/                         # RAG Pipeline
│   │   ├── pipeline.py                 # RAG orchestration
│   │   ├── context_builder.py          # Context assembly
│   │   └── response_generator.py       # Response generation
│   │
│   ├── 📂 cache/                       # Caching Layer
│   │   └── 📂 backends/
│   │       └── redis_cache.py          # Redis cache
│   │
│   ├── 📂 models/                      # Data Models
│   │   ├── schemas.py                  # Core schemas
│   │   ├── enhanced_schemas.py         # Enhanced financial schemas
│   │   └── vectordb_schemas.py         # Vector DB schemas
│   │
│   └── 📂 utils/                       # Utilities
│       ├── logging_config.py           # Logging setup
│       ├── metrics.py                  # Metrics collection
│       └── extraction_utils.py         # Extraction helpers
│
├── 📂 scripts/                         # Utility Scripts
│   ├── download_documents.py           # PDF downloader
│   ├── ingest_pipeline.py              # Batch ingestion
│   ├── verify_langchain.py             # LangChain verification
│   ├── verify_enrichment.py            # Metadata enrichment test
│   └── migrate_vectordb.py             # Vector DB migration
│
├── 📂 tests/                           # Test Suite
│   ├── test_extraction.py
│   ├── test_embeddings.py
│   ├── test_retrieval.py
│   └── test_rag.py
│
├── 📂 docs/                            # Documentation
│   └── (API docs, guides, etc.)
│
├── 📂 data/                            # Data Storage
│   ├── processed/                      # Processed data
│   └── cache/                          # Cache files
│
├── 📂 raw_data/                        # Raw PDF Files
│   └── (10-Q, 10-K PDFs)
│
├── 📂 faiss_index/                     # FAISS Vector Store
│   ├── index.faiss
│   └── metadata.pkl
│
├── 📂 chroma_db/                       # ChromaDB Vector Store
│
├── 📂 .logs/                           # Application Logs
│
└── 📂 archive/                         # Legacy/Archived Code
```

---

##  Quick Start

### 1. Environment Setup

```bash
# Clone/Navigate to project
cd /Users/nitin/Desktop/Chatbot/Morgan/GENAI

# Activate virtual environment
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your settings
```

### 2. Configuration

Edit `.env` to configure:
- **Vector Database**: `VECTORDB_PROVIDER=faiss` (or `chromadb`, `redis`)
- **Embeddings**: `EMBEDDING_PROVIDER=local` (or `openai`, `custom`)
- **LLM**: `LLM_PROVIDER=ollama` (or `openai`, `custom`)

---

## 📋 Available Commands

### Main Pipeline Commands

#### Download PDFs
```bash
# Download single quarter
python main.py download --yr 25 --m 03

# Download year range
python main.py download --yr 20-25

# Download all quarters for a year
python main.py download --yr 25
```

#### Extract Tables
```bash
# Extract from default directory (raw_data/)
python main.py extract

# Extract from custom directory
python main.py extract --source /path/to/pdfs

# Force re-extraction (ignore cache)
python main.py extract --force
```

#### Query System
```bash
# Single query
python main.py query "What was revenue in Q1 2025?"

# Interactive mode
python main.py interactive

# Advanced search (Hybrid/BM25/Vector)
python main.py search "Balance Sheet" --type hybrid --k 10
```

#### Complete Pipeline
```bash
# Download + Extract in one command
python main.py pipeline --yr 25 --m 03
```

#### System Utilities
```bash
# Show statistics
python main.py stats

# Clear cache
python main.py clear-cache

# Show help
python main.py --help
```

---

## 🔧 Advanced Usage

### Custom Extraction

```python
from src.extraction.extractor import UnifiedExtractor

extractor = UnifiedExtractor(
    backends=['docling', 'pymupdf'],
    min_quality=70.0,
    enable_caching=True
)

result = extractor.extract('document.pdf')
print(f"Tables: {len(result.tables)}")
print(f"Quality: {result.quality_score}")
```

### Hybrid Search

```python
from src.retrieval.retrievers import get_retriever

# Get hybrid retriever (Vector + BM25)
retriever = get_retriever(search_type="hybrid", k=10)

# Search
results = retriever.invoke("Balance Sheet Q1 2025")
for doc in results:
    print(doc.page_content)
    print(doc.metadata)
```

### Metadata Enrichment

```python
from src.extraction.enrichment import get_metadata_enricher

enricher = get_metadata_enricher()

metadata = enricher.enrich_table_metadata(
    content="(in millions) | Revenue | $100 |",
    table_title="Consolidated Balance Sheet"
)

print(metadata['units'])           # 'millions'
print(metadata['statement_type'])  # 'balance_sheet'
print(metadata['currency'])        # 'USD'
```

---

## 🧪 Testing & Verification

```bash
# Verify LangChain integration
python scripts/verify_langchain.py

# Verify metadata enrichment
python scripts/verify_enrichment.py

# Test extraction on sample PDF
python scripts/quick_test_extraction.py

# Run test suite
pytest tests/
```

---

## 📊 System Architecture

### Data Flow

```
PDF Documents
    ↓
[Extraction Layer]
    ├─ Docling (primary)
    ├─ PyMuPDF (fallback)
    └─ PDFPlumber (fallback)
    ↓
[Metadata Enrichment]
    ├─ Units detection
    ├─ Currency detection
    └─ Statement classification
    ↓
[Chunking Layer]
    └─ Smart table chunking (overlap)
    ↓
[Embedding Generation]
    ├─ Local (HuggingFace)
    ├─ OpenAI
    └─ Custom API
    ↓
[Vector Store]
    ├─ FAISS (fast)
    ├─ ChromaDB (persistent)
    └─ Redis (distributed)
    ↓
[Retrieval Layer]
    ├─ Vector Search (semantic)
    ├─ BM25 Search (keyword)
    └─ Hybrid Search (ensemble)
    ↓
[RAG Pipeline]
    ├─ Context assembly
    ├─ LLM generation
    └─ Response formatting
    ↓
User Query Response
```

### Key Features

- [DONE] **Multi-backend Extraction**: Automatic fallback if primary fails
- [DONE] **Rich Metadata**: 30+ fields per table (units, currency, statement type, etc.)
- [DONE] **Smart Chunking**: Overlapping chunks preserve context
- [DONE] **Hybrid Search**: Combines semantic + keyword search
- [DONE] **LangChain Native**: Full LangChain integration
- [DONE] **Configurable**: All settings via `.env` and `settings.py`
- [DONE] **Caching**: Extraction and query caching for performance

---

## 🔑 Environment Variables

See `.env.example` for full list. Key variables:

```bash
# Vector Database
VECTORDB_PROVIDER=faiss

# Embeddings
EMBEDDING_PROVIDER=local
EMBEDDING_MODEL_LOCAL=sentence-transformers/all-MiniLM-L6-v2

# LLM
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434

# Search
SEARCH_TOP_K=5
HYBRID_SEARCH_ALPHA=0.5

# Paths
RAW_DATA_DIR=/path/to/pdfs
```

---

## 📚 Additional Resources

- **Implementation Plan**: See `implementation_plan.md` in artifacts
- **Task Checklist**: See `task.md` in artifacts
- **Walkthrough**: See `walkthrough.md` in artifacts
- **README**: See `README.md` for project overview

---

## 🆘 Troubleshooting

### Import Errors
```bash
# Ensure virtual environment is activated
source .venv/bin/activate

# Reinstall dependencies
pip install -r requirements.txt
```

### FAISS Segmentation Fault
```bash
# Set environment variable
export KMP_DUPLICATE_LIB_OK=TRUE
```

### Missing PDFs
```bash
# Download PDFs first
python main.py download --yr 25
```

---

**Last Updated**: 2025-11-30  
**Version**: 2.0 (LangChain Orchestrated)
