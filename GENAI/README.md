# Financial RAG System 🚀

A production-ready **Retrieval Augmented Generation (RAG)** system for analyzing financial PDFs using **100% FREE local models**. No API keys required!

## ✨ Features

- 🆓 **Completely Free** - Uses local models (Ollama + sentence-transformers)
- 📄 **Advanced PDF Scraping** - Handles 2-column layouts, extracts tables with metadata
- 🧠 **Semantic Search** - ChromaDB vector database for intelligent retrieval
- ⚡ **Redis Caching** - Fast responses with intelligent caching
- 🏷️ **Rich Metadata** - SourceDoc, ChunkReferenceID, PageNo, Table_Title, Year, Quarter, and more
- 💬 **Interactive CLI** - Beautiful command-line interface
- 🎯 **Smart Filtering** - Query by year, quarter, table type

## 🛠️ Tech Stack

| Component | Technology | Why? |
|-----------|-----------|------|
| **LLM** | Ollama (llama3.2) | Free, local, no API keys |
| **Embeddings** | sentence-transformers | Free, local, fast |
| **Vector DB** | ChromaDB | Lightweight, embedded |
| **Cache** | Redis | Performance optimization |
| **Framework** | LangChain | Best for RAG pipelines |
| **PDF Parsing** | pdfplumber | Handles complex layouts |

## 📋 Prerequisites

### 1. Install Ollama (Free LLM)

```bash
# macOS
brew install ollama

# Start Ollama
ollama serve

# Pull the model (in a new terminal)
ollama pull llama3.2
```

### 2. Install Redis (Optional but recommended)

```bash
# macOS
brew install redis
brew services start redis
```

## 🚀 Quick Start

### 1. Install Dependencies

```bash
cd GENAI
pip install -r requirements.txt
```

### 2. Check System Setup

```bash
python main.py setup
```

This will verify:
- ✓ Ollama is running
- ✓ Redis is available
- ✓ Embedding model is loaded
- ✓ Vector store is ready

### 3. Index Your PDFs

```bash
# Index all PDFs from raw_data directory
python main.py index --source ../raw_data

# Clear existing index and rebuild
python main.py index --source ../raw_data --clear
```

**Expected output:**
```
📚 Indexing Financial PDFs

Found 6 PDF files

✓ 10k1224.pdf: 45 tables, 892 chunks (12.34s)
✓ 10q0320.pdf: 38 tables, 756 chunks (10.21s)
...

Indexing Summary
✓ Successfully processed: 6/6 files
✓ Total tables indexed: 234
✓ Total chunks created: 4,521
```

### 4. Query the System

```bash
# Simple query
python main.py query "What was the total revenue in Q2 2025?"

# Query with filters
python main.py query "Show balance sheet items" --year 2024 --quarter Q3

# Interactive mode
python main.py interactive
```

## 📖 Usage Examples

### Command Line Queries

```bash
# General question
python main.py query "What are the total assets?"

# Filtered by year
python main.py query "Show revenue breakdown" --year 2025

# Filtered by quarter
python main.py query "Cash flow analysis" --quarter Q2

# Retrieve more context
python main.py query "Compare balance sheets" --top-k 10

# Disable cache
python main.py query "Latest earnings" --no-cache
```

### Interactive Mode

```bash
python main.py interactive
```

Then ask questions naturally:
```
Your question: What was the total revenue in Q2 2025?
Your question: Show me all balance sheet items for 2024
Your question: Compare cash flow across quarters
```

### System Statistics

```bash
python main.py stats
```

Shows:
- Total chunks indexed
- Number of documents
- Years covered
- Cache statistics

### Clear Cache

```bash
python main.py clear-cache
```

### Rebuild Index

```bash
python main.py rebuild-index
```

## 📊 Metadata Schema

Each table chunk includes rich metadata:

```python
{
    "source_doc": "10q0625.pdf",           # Source PDF
    "chunk_reference_id": "uuid-here",     # Unique ID
    "page_no": 5,                          # Page number
    "table_title": "Consolidated Balance Sheet",
    "year": 2025,                          # Fiscal year
    "quarter": "Q2",                       # Quarter (for 10-Q)
    "report_type": "10-Q",                 # 10-K or 10-Q
    "table_type": "Balance Sheet",         # Classified type
    "fiscal_period": "June 30, 2025"       # Extracted period
}
```

## 🏗️ Architecture

```
┌─────────────┐
│   User      │
│   Query     │
└──────┬──────┘
       │
       ▼
┌─────────────────────────────────┐
│     Query Engine (RAG)          │
│  1. Parse query                 │
│  2. Extract filters             │
│  3. Check cache                 │
└──────┬──────────────────────────┘
       │
       ▼
┌─────────────────────────────────┐
│     Retriever                   │
│  - Semantic search              │
│  - Metadata filtering           │
│  - Context building             │
└──────┬──────────────────────────┘
       │
       ▼
┌─────────────────────────────────┐
│   Vector Store (ChromaDB)       │
│  - 4,521 chunks                 │
│  - Embeddings (384-dim)         │
│  - Metadata filters             │
└──────┬──────────────────────────┘
       │
       ▼
┌─────────────────────────────────┐
│   LLM (Ollama)                  │
│  - Generate answer              │
│  - Include citations            │
└──────┬──────────────────────────┘
       │
       ▼
┌─────────────┐
│  Response   │
│  + Sources  │
└─────────────┘
```

## 📁 Project Structure

```
GENAI/
├── config/
│   ├── settings.py          # Configuration
│   └── prompts.py           # LLM prompts
├── scrapers/
│   ├── pdf_scraper.py       # Enhanced PDF scraping
│   └── metadata_extractor.py # Metadata extraction
├── embeddings/
│   ├── embedding_manager.py # Embedding generation
│   └── vector_store.py      # ChromaDB operations
├── cache/
│   └── redis_cache.py       # Redis caching
├── rag/
│   ├── retriever.py         # Retrieval logic
│   ├── llm_manager.py       # LLM integration
│   └── query_engine.py      # Main RAG pipeline
├── models/
│   └── schemas.py           # Pydantic models
├── utils/
│   └── helpers.py           # Utility functions
├── main.py                  # CLI application
├── requirements.txt         # Dependencies
└── README.md               # This file
```

## ⚙️ Configuration

Edit `config/settings.py` or create a `.env` file:

```env
# LLM Settings
LLM_MODEL=llama3.2
LLM_TEMPERATURE=0.1
LLM_MAX_TOKENS=2000

# Embedding Settings
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2

# Redis Settings
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_ENABLED=true

# Retrieval Settings
TOP_K=5
SIMILARITY_THRESHOLD=0.7
```

## 🎯 Advanced Features

### Custom Filters

```python
from rag import get_query_engine

engine = get_query_engine()
response = engine.query(
    query="Show revenue",
    filters={
        "year": 2025,
        "quarter": "Q2",
        "table_type": "Income Statement"
    }
)
```

### Programmatic Usage

```python
from scrapers import EnhancedPDFScraper, MetadataExtractor
from embeddings import get_vector_store, get_embedding_manager

# Extract tables
scraper = EnhancedPDFScraper("path/to/file.pdf")
tables = scraper.extract_all_tables()

# Create chunks and index
# ... (see main.py for full example)
```

## 🐛 Troubleshooting

### Ollama not running

```bash
# Start Ollama
ollama serve

# In another terminal, pull the model
ollama pull llama3.2
```

### Redis connection failed

```bash
# Start Redis
brew services start redis

# Or disable Redis in settings
REDIS_ENABLED=false
```

### Embedding model download slow

The first run will download the sentence-transformers model (~90MB). This is a one-time download.

### Out of memory

Reduce batch size in `config/settings.py`:
```python
EMBEDDING_BATCH_SIZE=16  # Default is 32
```

## 📈 Performance

- **Indexing**: ~2-3 seconds per PDF
- **Query**: ~2-5 seconds (first query), <1 second (cached)
- **Embedding**: ~100 chunks/second
- **Memory**: ~500MB (embedding model) + ~200MB (vector DB)

## 🔒 Privacy

- ✅ All data stays on your machine
- ✅ No external API calls
- ✅ No data sent to cloud services
- ✅ Complete control over your data

## 🤝 Contributing

This is a production-ready system. Feel free to extend it with:
- Additional LLM models
- More sophisticated chunking strategies
- Custom metadata extractors
- API endpoints (FastAPI)
- Web UI

## 📝 License

MIT License - Use freely!

## 🙏 Acknowledgments

- **Ollama** - Free local LLM inference
- **sentence-transformers** - Free embeddings
- **ChromaDB** - Lightweight vector database
- **LangChain** - RAG framework
- **pdfplumber** - PDF parsing

---

**Built with ❤️ using 100% free and open-source tools**
