# GENAI Financial RAG System 

A production-ready **Retrieval Augmented Generation (RAG)** system for analyzing financial PDFs, built on a **Unified LangChain Architecture**.

## ✨ Key Features

- **Unified LangChain System** - Standardized Embeddings, Vector Store, and RAG Chains (LCEL)
- **Advanced PDF Processing** - Intelligent table extraction with Docling
- **Smart Embeddings** - Multi-level embeddings (table, row, cell)
- **Vector Storage** - ChromaDB (LangChain wrapper) for semantic search
- **Clean Architecture** - Enterprise-level code organization with standardized logging
- **100% Local** - No API keys required (Ollama + HuggingFace)

## 📋 Quick Start

### 1. Setup

```bash
cd /Users/nitin/Desktop/Chatbot/Morgan/GENAI

# Activate virtual environment
source ../.venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Extract & Index PDFs

```bash
# Extract tables from PDFs
python main.py extract --source raw_data

# Download and extract
python main.py pipeline --yr 25 --m 03
```

### 3. Query the System

```bash
# Simple query
python main.py query "What was revenue in Q1 2025?"

# Interactive mode
python main.py interactive
```

## 🏗️ Project Structure

```
GENAI/
├── src/                        # Main source code
│   ├── models/                 # Data models & schemas
│   ├── extraction/             # PDF extraction system
│   │   ├── backends/           # Docling, PyMuPDF, etc.
│   │   └── extractor.py        # Main extractor
│   ├── embeddings/             # Embedding generation
│   │   └── manager.py          # LangChain Embedding Manager
│   ├── vector_store/           # Vector database
│   │   └── stores/             # LangChain Chroma Wrapper
│   ├── retrieval/              # Query & retrieval
│   ├── rag/                    # RAG pipeline (LCEL)
│   ├── llm/                    # LLM integration (ChatOllama)
│   ├── cache/                  # Caching layer
│   └── utils/                  # Utilities (Logging, etc.)
│
├── config/                     # Configuration
├── scripts/                    # Utility scripts
├── examples/                   # Usage examples
├── tests/                      # Test suite
├── archive/                    # Archived old code
├── docs/                       # Documentation
│
├── main.py                     # CLI Application
├── requirements.txt            # Dependencies
└── README.md                   # This file
```

## 📖 Documentation

- **[GETTING_STARTED.md](GETTING_STARTED.md)** - Detailed setup
- **[SYSTEM_OVERVIEW.md](SYSTEM_OVERVIEW.md)** - Architecture overview
- **[SEARCH_SYSTEM_GUIDE.md](SEARCH_SYSTEM_GUIDE.md)** - Search strategies
- **[LANGCHAIN_INTEGRATION_STRATEGY.md](LANGCHAIN_INTEGRATION_STRATEGY.md)** - Integration status
- **[REPOSITORY_AUDIT.md](REPOSITORY_AUDIT.md)** - Code quality audit

## 🔧 Configuration

All imports now use the `src.` prefix and standard LangChain interfaces:

```python
# Embeddings (LangChain)
from src.embeddings.manager import get_embedding_manager

# Vector Store (LangChain)
from src.vector_store.stores.chromadb_store import get_vector_store

# Logging
from src.utils.logging_config import get_logger
logger = get_logger(__name__)
```

## ⚡ Recent Updates

### Unified LangChain Architecture
- [DONE] **Embeddings:** Implemented `Embeddings` interface
- [DONE] **Vector Store:** Wrapped `langchain_community.vectorstores.Chroma`
- [DONE] **RAG Pipeline:** Migrated to LCEL (`RunnableParallel`)
- [DONE] **LLM:** Integrated `ChatOllama`

### Enterprise-Level Improvements
- [DONE] **Logging:** Centralized structured logging (no more `print`)
- [DONE] **Error Handling:** Robust exception management
- [DONE] **Architecture:** Fixed circular imports and dependency injection

See [walkthrough.md](file:///Users/nitin/.gemini/antigravity/brain/e934d782-e8fc-47a7-af49-8ca5e598f1fc/walkthrough.md) for complete details.

## 🤝 Contributing

Contributions welcome! The codebase now follows enterprise-level standards.

## 📝 License

MIT License - Use freely!

---

**Built with ❤️ using open-source tools**
