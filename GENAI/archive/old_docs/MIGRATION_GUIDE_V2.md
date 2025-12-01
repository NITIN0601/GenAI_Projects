# GENAI Restructuring - Quick Migration Guide

## 🚀 Quick Start

Your GENAI project has been restructured! Here's what you need to know:

## ✅ What Changed

### Directory Structure
- **Old**: Files scattered across `/extraction`, `/embeddings`, `/rag`, `/data_processing`
- **New**: Everything organized under `/src` with clear module separation

### Import Paths
All imports now start with `src.`:
```python
# ❌ Old
from extraction import UnifiedExtractor
from embeddings.embedding_manager import EmbeddingManager
from rag.query_engine import QueryEngine

# ✅ New
from src.extraction.extractor import UnifiedExtractor as Extractor
from src.embeddings.manager import EmbeddingManager
from src.rag.pipeline import QueryEngine as RAGPipeline
```

## 📝 Common Import Patterns

### Extraction
```python
from src.extraction.extractor import UnifiedExtractor as Extractor
from src.extraction import extract_pdf  # Quick extraction function
```

### Embeddings
```python
from src.embeddings.manager import EmbeddingManager
from src.embeddings.multi_level import MultiLevelEmbeddingGenerator
```

### Vector Store
```python
from src.vector_store.manager import VectorStoreManager
from src.vector_store.stores.chromadb_store import VectorStore
```

### LLM
```python
from src.llm.manager import LLMManager
```

### Retrieval
```python
from src.retrieval.retriever import Retriever
from src.retrieval.query_processor import QueryProcessor
```

### RAG Pipeline
```python
from src.rag.pipeline import QueryEngine as RAGPipeline
```

### Utilities
```python
from src.utils import get_logger
from src.utils.exceptions import ExtractionError, EmbeddingError
```

## 🔧 Configuration

The `config/settings.py` has been updated with new paths:
- `SRC_DIR` - Source code directory
- `SCRIPTS_DIR` - Entry point scripts
- `DATA_DIR` - Data storage (raw, processed, cache)
- `ARCHIVE_DIR` - Archived old files

Legacy paths are still available for backward compatibility during migration.

## 📂 Where Things Are Now

| Component | Old Location | New Location |
|-----------|-------------|--------------|
| Extraction | `/extraction`, `/data_processing/extraction` | `/src/extraction` |
| Embeddings | `/embeddings` | `/src/embeddings` |
| Vector Store | `/embeddings` (mixed) | `/src/vector_store` |
| LLM | `/rag` (mixed) | `/src/llm` |
| Retrieval | `/rag` (mixed) | `/src/retrieval` |
| RAG Pipeline | `/rag` | `/src/rag` |
| Scrapers | `/scrapers`, `/data_processing/scrapers` | `/src/ingestion/scrapers` |
| Scripts | Root directory | `/scripts` |
| Utilities | `/utils`, scattered | `/src/utils` |

## 🗂️ Scripts

Top-level scripts have been moved to `/scripts`:
- `download.py` → `scripts/download_documents.py`
- `production_pipeline.py` → `scripts/ingest_pipeline.py`
- `pipeline_extract_to_vectordb.py` → `scripts/extract_to_vectordb.py`
- `vectordb_migrate.py` → `scripts/migrate_vectordb.py`

## 📦 Archive

All old files are preserved in `/archive`:
- `archive/old_extraction/` - Old extraction wrapper
- `archive/old_scripts/` - Old top-level scripts
- `archive/embeddings/` - Old embeddings module
- `archive/rag/` - Old RAG module
- `archive/data_processing/` - Old data processing
- `archive/unwanted/` - Unwanted files

**Nothing was deleted!** You can recover any file if needed.

## ⚠️ Breaking Changes

1. **Import paths changed** - All imports must be updated
2. **Module names changed** - Some files renamed for clarity:
   - `unified_extractor.py` → `extractor.py`
   - `embedding_manager.py` → `manager.py`
   - etc.
3. **Directory structure changed** - Files moved to new locations

## ✅ Migration Checklist

- [ ] Update import statements in your scripts
- [ ] Update import statements in notebooks
- [ ] Test extraction functionality
- [ ] Test embedding generation
- [ ] Test RAG pipeline
- [ ] Update any custom scripts
- [ ] Update documentation
- [ ] Remove `/archive` once verified (optional)

## 🆘 Troubleshooting

### Import Error: "No module named 'extraction'"
**Solution**: Update import to use `src.extraction`
```python
# Change this:
from extraction import UnifiedExtractor
# To this:
from src.extraction.extractor import UnifiedExtractor as Extractor
```

### Import Error: "No module named 'data_processing'"
**Solution**: Old import path, update to new structure
```python
# Change this:
from data_processing.extraction import UnifiedExtractor
# To this:
from src.extraction.extractor import UnifiedExtractor as Extractor
```

### Circular Import Error
**Solution**: Use direct imports instead of package-level imports
```python
# Instead of:
from src.extraction import Extractor  # May cause circular import
# Use:
from src.extraction.extractor import UnifiedExtractor as Extractor
```

## 📞 Need Help?

1. Check the complete report: `walkthrough.md`
2. Review the implementation plan: `implementation_plan.md`
3. Look at archived files in `/archive` for reference

## 🎉 Benefits

After migration, you'll have:
- ✅ No circular imports
- ✅ Clear module boundaries
- ✅ Professional naming conventions
- ✅ Easier to maintain and scale
- ✅ Better IDE support and autocomplete
