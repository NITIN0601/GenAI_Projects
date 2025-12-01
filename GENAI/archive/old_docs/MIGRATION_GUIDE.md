# Migration Guide: Old Extraction → Unified System

## Overview

This guide helps you migrate from the old extraction system to the new unified extraction system.

---

## Quick Migration

### Before (Old System)

```python
# Option 1: extract_page_by_page.py
from extract_page_by_page import PageByPageExtractor

extractor = PageByPageExtractor("document.pdf")
result = extractor.extract_document()
chunks = result['chunks']
```

```python
# Option 2: scrapers/docling_scraper.py
from scrapers.docling_scraper import DoclingPDFScraper

scraper = DoclingPDFScraper("document.pdf")
document = scraper.extract_document()
tables = document.tables
```

### After (New System)

```python
from extraction import UnifiedExtractor

# Simple usage
extractor = UnifiedExtractor()
result = extractor.extract("document.pdf")
tables = result.tables
```

---

## Detailed Migration

### 1. Basic Extraction

**OLD:**
```python
from extract_page_by_page import PageByPageExtractor

extractor = PageByPageExtractor(pdf_path)
result = extractor.extract_document()

for chunk in result['chunks']:
    print(chunk.content)
```

**NEW:**
```python
from extraction import UnifiedExtractor

extractor = UnifiedExtractor()
result = extractor.extract(pdf_path)

for table in result.tables:
    print(table['content'])
```

### 2. Batch Processing

**OLD:**
```python
from extract_page_by_page import extract_pdfs_batch

results = extract_pdfs_batch(
    pdf_dir="../raw_data",
    force=False
)
```

**NEW:**
```python
from extraction import UnifiedExtractor
from pathlib import Path

extractor = UnifiedExtractor()
pdf_paths = list(Path("../raw_data").glob("*.pdf"))
results = extractor.extract_batch(pdf_paths)
```

### 3. With Caching

**OLD:**
```python
# Caching was implicit in old system
extractor = PageByPageExtractor(pdf_path)
result = extractor.extract_document()
```

**NEW:**
```python
# Explicit caching control
extractor = UnifiedExtractor(
    enable_caching=True,
    cache_ttl_hours=24
)

# First extraction (slow)
result1 = extractor.extract(pdf_path)

# Second extraction (fast, from cache)
result2 = extractor.extract(pdf_path)

# Force re-extraction
result3 = extractor.extract(pdf_path, force=True)
```

### 4. Custom Configuration

**OLD:**
```python
from embeddings.table_chunker import TableChunker

chunker = TableChunker(
    chunk_size=10,
    overlap=3,
    flatten_headers=False
)
```

**NEW:**
```python
# Pass options to backend
extractor = UnifiedExtractor(
    chunk_size=10,
    overlap=3,
    flatten_headers=False
)
```

### 5. Production Pipeline

**OLD (production_pipeline.py):**
```python
from scrapers.docling_scraper import DoclingPDFScraper

scraper = DoclingPDFScraper(pdf_path)
document = scraper.extract_document()
```

**NEW:**
```python
from extraction import UnifiedExtractor

extractor = UnifiedExtractor(
    backends=["docling"],
    enable_caching=True
)
result = extractor.extract(pdf_path)
```

---

## Result Format Changes

### Old Format (extract_page_by_page.py)

```python
result = {
    'chunks': [TableChunk, ...],
    'total_tables': int,
    'total_chunks': int,
    'extraction_time': float
}
```

### New Format (UnifiedExtractor)

```python
result = ExtractionResult(
    tables=[{
        'content': str,
        'metadata': {...}
    }, ...],
    backend=BackendType.DOCLING,
    quality_score=85.0,
    extraction_time=32.5,
    metadata={...}
)
```

### Accessing Data

**OLD:**
```python
for chunk in result['chunks']:
    content = chunk.content
    metadata = chunk.metadata
```

**NEW:**
```python
for table in result.tables:
    content = table['content']
    metadata = table['metadata']
```

---

## Feature Mapping

| Old Feature | New Feature | Notes |
|-------------|-------------|-------|
| `PageByPageExtractor` | `UnifiedExtractor` | More features, same quality |
| `DoclingPDFScraper` | `DoclingBackend` | Used internally |
| Manual caching | `ExtractionCache` | Automatic, configurable |
| Single backend | Multiple backends | Automatic fallback |
| No quality check | `QualityAssessor` | 0-100 score |

---

## Benefits of New System

### ✅ Multiple Backends
- Docling (default)
- PyMuPDF (fallback)
- Easy to add more

### ✅ Automatic Fallback
- Tries backends in priority order
- Quality-based selection
- Returns best result

### ✅ Quality Assessment
- Comprehensive scoring
- Multiple metrics
- Configurable thresholds

### ✅ Better Caching
- File-based with TTL
- Automatic cleanup
- Cache statistics

### ✅ All Improvements Preserved
- Chunking with overlap
- Spanning headers
- Multi-line headers
- Metadata extraction

---

## Deprecated Files

The following files are deprecated:

1. **extract_page_by_page.py** ⚠️
   - Status: Deprecated with warning
   - Action: Use `extraction.UnifiedExtractor`
   - Timeline: Will be removed in future version

2. **extract_structure_correct.py** ⚠️
   - Status: Moved to unwanted/
   - Action: Use `extraction.UnifiedExtractor`
   - Timeline: Removed from active codebase

3. **scrapers/docling_scraper.py** ⚠️
   - Status: Deprecated (still used by old code)
   - Action: Use `extraction.backends.DoclingBackend`
   - Timeline: Will be removed after migration complete

---

## Migration Checklist

- [ ] Update imports to use `extraction` module
- [ ] Replace `PageByPageExtractor` with `UnifiedExtractor`
- [ ] Replace `DoclingPDFScraper` with `UnifiedExtractor`
- [ ] Update result handling (chunks → tables)
- [ ] Test extraction on sample PDFs
- [ ] Update tests to use new system
- [ ] Remove old extraction code
- [ ] Update documentation

---

## Troubleshooting

### Import Error
```python
# Error: ModuleNotFoundError: No module named 'extraction'
# Solution: Make sure you're in the GENAI directory
import sys
sys.path.insert(0, '/Users/nitin/Desktop/Chatbot/Morgan/GENAI')
from extraction import UnifiedExtractor
```

### Backend Not Available
```python
# Check available backends
extractor = UnifiedExtractor()
print(extractor.get_stats()['available_backends'])
```

### Low Quality Scores
```python
# Lower threshold or check PDF quality
extractor = UnifiedExtractor(min_quality=50.0)
```

---

## Support

For questions or issues:
1. Check `docs/UNIFIED_EXTRACTION.md`
2. Run tests: `python3 tests/integration/test_unified_extraction.py`
3. Review `CONSOLIDATION_PLAN.md`

---

## Timeline

- **Now**: Old system deprecated with warnings
- **Next week**: All code migrated to new system
- **Next month**: Old files removed

Start migrating today! 🚀
