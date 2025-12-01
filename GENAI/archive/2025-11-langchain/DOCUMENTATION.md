# Documentation Guide

Welcome to the GENAI Financial Document Processing & RAG System documentation!

## 🚀 Getting Started

**New to the project?** Start here:

1. **[README.md](README.md)** - Project overview and key features
2. **[GETTING_STARTED.md](GETTING_STARTED.md)** - Quick start guide with setup instructions
3. **[USAGE_GUIDE.md](USAGE_GUIDE.md)** - Learn when to use `/extraction` vs `/scrapers`

## 📖 Core Documentation

### System Architecture
- **[SYSTEM_OVERVIEW.md](SYSTEM_OVERVIEW.md)** - Visual guide to the extraction pipeline and system components
- **[ENTERPRISE_FEATURES.md](ENTERPRISE_FEATURES.md)** - Production-ready features (logging, metrics, monitoring)

### Usage & Migration
- **[USAGE_GUIDE.md](USAGE_GUIDE.md)** - Detailed usage examples and decision tree
- **[MIGRATION_GUIDE.md](MIGRATION_GUIDE.md)** - Migrating from old extraction system to unified system

## 🔧 Technical Documentation

### Extraction System
- **[docs/UNIFIED_EXTRACTION.md](docs/UNIFIED_EXTRACTION.md)** - Complete unified extraction system documentation
  - Multiple backends (Docling, PyMuPDF, pdfplumber, Camelot)
  - Automatic fallback strategy
  - Quality assessment
  - Caching system

### Table Processing
- **[docs/CHUNKING_STRATEGY.md](docs/CHUNKING_STRATEGY.md)** - Intelligent chunking with overlap for vector search
- **[docs/MULTILINE_HEADER_HANDLING.md](docs/MULTILINE_HEADER_HANDLING.md)** - Multi-line header flattening and spanning headers
- **[docs/TABLE_STRUCTURE_PRESERVATION.md](docs/TABLE_STRUCTURE_PRESERVATION.md)** - How table structure is maintained in chunks

### Testing & Results
- **[docs/TEST_RESULTS.md](docs/TEST_RESULTS.md)** - Real PDF extraction test results and examples

## 🛠️ Component Documentation

- **[scripts/README.md](scripts/README.md)** - Utility scripts for development and testing
- **[tests/README.md](tests/README.md)** - Test organization (unit, integration, system tests)
- **[docs/README.md](docs/README.md)** - Technical documentation index

## 📁 Documentation Structure

```
GENAI/
├── README.md                          # Main entry point
├── DOCUMENTATION.md                   # This file
├── GETTING_STARTED.md                 # Quick start guide
├── USAGE_GUIDE.md                     # Usage examples
├── SYSTEM_OVERVIEW.md                 # System architecture
├── MIGRATION_GUIDE.md                 # Migration guide
├── ENTERPRISE_FEATURES.md             # Enterprise features
│
├── docs/                              # Technical documentation
│   ├── README.md
│   ├── UNIFIED_EXTRACTION.md
│   ├── CHUNKING_STRATEGY.md
│   ├── MULTILINE_HEADER_HANDLING.md
│   ├── TABLE_STRUCTURE_PRESERVATION.md
│   └── TEST_RESULTS.md
│
├── scripts/
│   └── README.md
│
└── tests/
    └── README.md
```

## 🔍 Quick Navigation

### I want to...

**...understand the system**
→ Start with [README.md](README.md) then [SYSTEM_OVERVIEW.md](SYSTEM_OVERVIEW.md)

**...set up and run the system**
→ Follow [GETTING_STARTED.md](GETTING_STARTED.md)

**...extract tables from PDFs**
→ See [USAGE_GUIDE.md](USAGE_GUIDE.md) and [docs/UNIFIED_EXTRACTION.md](docs/UNIFIED_EXTRACTION.md)

**...understand extraction vs processing**
→ Read [USAGE_GUIDE.md](USAGE_GUIDE.md) and [SYSTEM_OVERVIEW.md](SYSTEM_OVERVIEW.md)

**...migrate from old system**
→ Follow [MIGRATION_GUIDE.md](MIGRATION_GUIDE.md)

**...understand enterprise features**
→ Read [ENTERPRISE_FEATURES.md](ENTERPRISE_FEATURES.md)

**...run tests**
→ See [tests/README.md](tests/README.md)

**...understand table processing**
→ Check [docs/CHUNKING_STRATEGY.md](docs/CHUNKING_STRATEGY.md) and related docs

## 📚 Additional Resources

### Archive
Historical documentation and consolidation records are preserved in:
- `archive/consolidation/` - Consolidation process documentation
- `archive/old_docs/` - Old development and analysis documents

### External Links
- [Docling Documentation](https://github.com/DS4SD/docling) - Advanced PDF parsing
- [Ollama Documentation](https://ollama.ai/) - Local LLM inference
- [ChromaDB Documentation](https://docs.trychroma.com/) - Vector database

---

**Questions?** Start with [README.md](README.md) or [GETTING_STARTED.md](GETTING_STARTED.md)

**Need help?** Check the relevant documentation section above or review the [USAGE_GUIDE.md](USAGE_GUIDE.md)
