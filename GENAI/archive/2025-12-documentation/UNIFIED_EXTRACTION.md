# Unified Extraction System

## Overview

The unified extraction system provides a scalable, extensible PDF extraction framework with multiple backends, automatic quality assessment, intelligent fallback, and caching.

## Features

✅ **Multiple Backends**
- Docling (default) - Best for complex financial tables
- PyMuPDF (fallback) - Fast, lightweight alternative
- Easy to add new backends

✅ **Automatic Fallback**
- Tries backends in priority order
- Quality-based selection
- Returns best result

✅ **Quality Assessment**
- Comprehensive scoring (0-100)
- Multiple metrics (table count, completeness, structure, text quality)
- Configurable thresholds

✅ **Caching**
- File-based cache with TTL
- Avoid re-extraction
- Significant time savings

✅ **All Table Improvements**
- Intelligent chunking with overlap
- Centered spanning headers
- Multi-line header flattening
- Complete metadata extraction

## Quick Start

### Basic Usage

```python
from extraction import extract_pdf

# Simple extraction
result = extract_pdf("document.pdf")

print(f"Backend: {result.backend.value}")
print(f"Quality: {result.quality_score:.1f}")
print(f"Tables: {len(result.tables)}")
```

### Advanced Usage

```python
from extraction import UnifiedExtractor

# Custom configuration
extractor = UnifiedExtractor(
    backends=["docling", "pymupdf"],  # Specify backends
    min_quality=75.0,                  # Quality threshold
    enable_caching=True,               # Enable caching
    cache_ttl_hours=24                 # Cache TTL
)

# Extract with fallback
result = extractor.extract("document.pdf")

# Get statistics
stats = extractor.get_stats()
print(stats)
```

### Batch Processing

```python
from extraction import UnifiedExtractor

extractor = UnifiedExtractor()

# Extract multiple PDFs
pdf_paths = ["doc1.pdf", "doc2.pdf", "doc3.pdf"]
results = extractor.extract_batch(pdf_paths)

for result in results:
    print(f"{result.pdf_path}: {len(result.tables)} tables")
```

## Architecture

```
extraction/
├── __init__.py              # Main exports
├── base.py                  # Base interfaces
├── unified_extractor.py     # Main extractor
├── strategy.py              # Fallback strategy
├── quality.py               # Quality assessment
├── cache.py                 # Caching mechanism
└── backends/
    ├── __init__.py
    ├── docling_backend.py   # Docling implementation
    └── pymupdf_backend.py   # PyMuPDF implementation
```

## Backends

### Docling (Priority 1)
- **Best for**: Complex financial tables
- **Features**: ML-based, structure preservation, chunking
- **Quality**: 85+ base score

### PyMuPDF (Priority 2)
- **Best for**: Simple tables, fast extraction
- **Features**: Lightweight, text-based
- **Quality**: 70+ base score

## Quality Metrics

Quality score (0-100) based on:
- **Table count** (20 points) - Number of tables found
- **Cell completeness** (30 points) - % of non-empty cells
- **Structure** (25 points) - Headers, consistent columns
- **Text quality** (15 points) - No garbled text
- **Backend confidence** (10 points) - Backend-specific score

### Quality Grades
- **Excellent**: 90-100
- **Good**: 75-89
- **Fair**: 60-74
- **Poor**: 0-59

## Fallback Strategy

```
1. Try Docling (quality >= 80?)
   ├─ Yes → Use result ✓
   └─ No → Try fallback

2. Try PyMuPDF (quality >= 70?)
   ├─ Yes → Use result ✓
   └─ No → Try fallback

3. Return best result from all attempts
```

## Caching

### File-Based Cache
- **Location**: `.cache/extraction/`
- **Format**: Pickle files
- **TTL**: 24 hours (configurable)
- **Key**: MD5(path + mtime)

### Cache Operations

```python
extractor = UnifiedExtractor(enable_caching=True)

# Get cache stats
stats = extractor.get_stats()
print(stats['cache'])

# Clear cache
count = extractor.clear_cache()
print(f"Deleted {count} files")

# Force re-extraction
result = extractor.extract("doc.pdf", force=True)
```

## Configuration

### Environment Variables
```bash
# Cache settings
EXTRACTION_CACHE_ENABLED=true
EXTRACTION_CACHE_TTL_HOURS=24

# Quality thresholds
EXTRACTION_MIN_QUALITY=60.0

# Backends
EXTRACTION_BACKENDS=docling,pymupdf
```

### Programmatic Configuration
```python
extractor = UnifiedExtractor(
    backends=["docling", "pymupdf"],
    min_quality=75.0,
    enable_caching=True,
    cache_ttl_hours=48,
    # Backend-specific options
    chunk_size=10,
    overlap=3,
    flatten_headers=False
)
```

## Testing

Run tests:
```bash
cd /Users/nitin/Desktop/Chatbot/Morgan/GENAI
python3 tests/integration/test_unified_extraction.py
```

## Adding New Backends

1. Create backend class:
```python
from extraction.base import ExtractionBackend, ExtractionResult, BackendType

class MyBackend(ExtractionBackend):
    def extract(self, pdf_path: str, **kwargs) -> ExtractionResult:
        # Implementation
        pass
    
    def get_name(self) -> str:
        return "MyBackend"
    
    def get_backend_type(self) -> BackendType:
        return BackendType.CUSTOM
    
    def is_available(self) -> bool:
        return True
    
    def get_priority(self) -> int:
        return 3
```

2. Register in `unified_extractor.py`:
```python
available = {
    'docling': DoclingBackend,
    'pymupdf': PyMuPDFBackend,
    'mybackend': MyBackend,  # Add here
}
```

3. Use it:
```python
extractor = UnifiedExtractor(backends=["mybackend"])
```

## Performance

### Benchmarks (10k1222-1-20.pdf, 20 pages)

| Backend | Time | Tables | Quality |
|---------|------|--------|---------|
| Docling | 32s  | 2      | 85.0    |
| PyMuPDF | 5s   | 2      | 70.0    |

### Caching Impact
- **First extraction**: 32s
- **Cached extraction**: <0.1s
- **Speedup**: 320x

## Troubleshooting

### Backend not available
```python
# Check available backends
extractor = UnifiedExtractor()
print(extractor.get_stats()['available_backends'])
```

### Low quality scores
```python
# Lower threshold or check PDF quality
extractor = UnifiedExtractor(min_quality=50.0)
```

### Cache issues
```python
# Clear cache
extractor.clear_cache()

# Disable caching
extractor = UnifiedExtractor(enable_caching=False)
```

## Migration from Old System

### Before
```python
from extract_page_by_page import PageByPageExtractor

extractor = PageByPageExtractor("doc.pdf")
result = extractor.extract_document()
```

### After
```python
from extraction import extract_pdf

result = extract_pdf("doc.pdf")
```

## Future Enhancements

- [ ] Redis caching backend
- [ ] Parallel extraction with multiprocessing
- [ ] ML-based backend selection
- [ ] pdfplumber backend
- [ ] Camelot backend
- [ ] Custom extraction strategies
- [ ] Metrics dashboard
