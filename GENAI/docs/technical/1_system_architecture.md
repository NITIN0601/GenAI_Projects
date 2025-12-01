# Complete System Overview

## `/extraction` vs `/scrapers` - Visual Guide

### The Pipeline

```
┌──────────────┐
│   PDF FILE   │  10k1224.pdf, 10q0625.pdf
└──────┬───────┘
       │
       │ ┌─────────────────────────────────────────┐
       └─┤  STEP 1: EXTRACTION (/extraction/)      │
         │  "Get tables OUT of PDFs"               │
         │                                          │
         │  Input:  PDF file                        │
         │  Output: Raw markdown tables             │
         │  Tools:  4 backends (Docling, PyMuPDF,  │
         │          pdfplumber, Camelot)            │
         └──────────────┬───────────────────────────┘
                        │
                        ▼
         ┌──────────────────────────────┐
         │   RAW TABLES (Markdown)      │
         │                              │
         │  | Assets | 2024 | 2023 |   │
         │  |--------|------|------|   │
         │  | Cash   | 100M | 90M  |   │
         │  | Loans  | 500M | 450M |   │
         └──────────────┬───────────────┘
                        │
       ┌────────────────┴────────────────┐
       │                                 │
       │  OPTIONAL: Need processing?     │
       │                                 │
       ├─ NO  → Use raw tables           │
       │                                 │
       └─ YES → Continue to Step 2       │
                        │
                        ▼
         ┌─────────────────────────────────────────┐
         │  STEP 2: PROCESSING (/scrapers/)        │
         │  "Process and normalize data"           │
         │                                          │
         │  A. metadata_extractor.py                │
         │     Extract: year, quarter, report type  │
         │                                          │
         │  B. label_normalizer.py                  │
         │     "Cash" → "cash_and_equivalents"     │
         │                                          │
         │  C. period_parser.py                     │
         │     "June 30, 2024" → Date object       │
         │                                          │
         │  D. unit_converter.py                    │
         │     "100M" → 100,000,000                │
         └──────────────┬───────────────────────────┘
                        │
                        ▼
         ┌──────────────────────────────┐
         │  NORMALIZED DATA             │
         │                              │
         │  {                           │
         │    year: 2024,               │
         │    report_type: "10-K",      │
         │    rows: [                   │
         │      {                       │
         │        label: "cash_and_...",│
         │        value: 100000000      │
         │      }                       │
         │    ]                         │
         │  }                           │
         └──────────────┬───────────────┘
                        │
                        ▼
         ┌──────────────────────────────┐
         │  VECTOR DATABASE             │
         │  or ANALYSIS                 │
         └──────────────────────────────┘
```

---

## Quick Reference

### Use `/extraction/` when:
- [DONE] You have PDF files
- [DONE] You need to extract tables
- [DONE] You want raw table data
- [DONE] First step in pipeline

### Use `/scrapers/` when:
- [DONE] You have extracted tables
- [DONE] You need to normalize labels
- [DONE] You need metadata (year, quarter)
- [DONE] You need to convert units
- [DONE] Second step in pipeline

---

## Code Examples

### Extraction Only
```python
from extraction import UnifiedExtractor

extractor = UnifiedExtractor()
result = extractor.extract("10k1224.pdf")

# Use raw tables
for table in result.tables:
    print(table['content'])
```

### Extraction + Processing
```python
from extraction import UnifiedExtractor
from scrapers.metadata_extractor import MetadataExtractor
from scrapers.label_normalizer import get_label_normalizer

# Step 1: Extract
extractor = UnifiedExtractor()
result = extractor.extract("10k1224.pdf")

# Step 2: Process
metadata_ext = MetadataExtractor("10k1224.pdf")
normalizer = get_label_normalizer()

for table in result.tables:
    # Get metadata
    metadata = metadata_ext.extract_metadata(
        table['metadata']['table_title'],
        table['metadata']['page_no']
    )
    
    # Normalize labels
    # ... process rows
```

---

## RAG Pipeline Architecture (Unified LangChain)

The system uses a modern **LangChain LCEL (LangChain Expression Language)** pipeline for robust retrieval and generation.

```
┌─────────────────┐
│   USER QUERY    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  RAG PIPELINE   │ (src/rag/pipeline.py)
│                 │
│  1. Retrieval   │ ← LangChain Retriever (Chroma/Ensemble)
│  2. Prompting   │ ← PromptTemplate
│  3. Generation  │ ← ChatOllama (LLM)
│  4. Parsing     │ ← StrOutputParser
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│    RESPONSE     │
└─────────────────┘
```

---

## Summary

| | /extraction | /scrapers | /rag |
|---|---|---|---|
| **Purpose** | Extract tables | Process data | Answer questions |
| **Input** | PDF files | Tables | User Query |
| **Output** | Raw tables | Normalized data | Answer + Citations |
| **Stage** | 1st (extraction) | 2nd (processing) | 3rd (inference) |
| **Tech** | Docling | Pandas | LangChain LCEL |

**They work together but are independent!** 

---

# Caching Architecture
# Extraction Cache System - Complete Guide

## Overview

The extraction system automatically caches all extracted tables to avoid re-extraction. This significantly speeds up repeated processing of the same PDFs.

---

## Cache Location

**Directory**: `/GENAI/.cache/extraction/`

**Current Cache**:
```
.cache/extraction/
├── 0ce6ec71b25694c2c96056abae02dc2d.pkl  (753 KB)
├── 2e8c9fe2d1c260c3eafb7d66491c562f.pkl  (787 KB)
├── 36f89bc8eb48cf243525642c68524476.pkl  (832 KB)
├── 42d8283071c1fe542b0552f959794625.pkl  (617 KB)
├── 860e1542f67095f7108493bab9eeaf4d.pkl  (7 KB)
├── 8eca0bbe256090ce991061397b49cafb.pkl  (2 KB)
└── cfc9406b3d4038810d1d34d53de1a29c.pkl  (794 KB)
```

**Total**: 7 cached PDFs (~3.7 MB)

---

## How Caching Works

### 1. Cache Key Generation

Each PDF gets a unique cache key based on:
- **File path** (absolute path)
- **Modification time** (detects file changes)

```python
# From cache.py
def _get_cache_key(self, pdf_path: str) -> str:
    pdf_file = Path(pdf_path)
    key_data = f"{pdf_file.absolute()}_{pdf_file.stat().st_mtime}"
    return hashlib.md5(key_data.encode()).hexdigest()
```

**Example**:
- PDF: `/Morgan/raw_data/10k1222.pdf`
- Modified: `1701234567.89`
- Cache Key: `cfc9406b3d4038810d1d34d53de1a29c`
- Cache File: `cfc9406b3d4038810d1d34d53de1a29c.pkl`

### 2. What Gets Cached

The entire `ExtractionResult` object is saved, including:

```python
{
    'backend': 'docling',
    'pdf_path': '/path/to/file.pdf',
    'tables': [
        {
            'content': '| Header1 | Header2 |\n|---------|---------|...',
            'metadata': {
                'page_no': 1,
                'table_title': 'Financial Summary',
                'year': 2022,
                'quarter': 'Q4',
                'report_type': '10-K'
            }
        },
        # ... more tables
    ],
    'quality_score': 85.0,
    'extraction_time': 60.5,
    'page_count': 150,
    'metadata': {...}
}
```

### 3. Cache Lifecycle

```
┌─────────────────┐
│  extract(pdf)   │
└────────┬────────┘
         │
         ▼
    ┌─────────┐
    │ Cache?  │──Yes──▶ Return cached result (instant!)
    └────┬────┘
         │ No
         ▼
    ┌──────────┐
    │ Extract  │ (60-800 seconds)
    └────┬─────┘
         │
         ▼
    ┌──────────┐
    │  Cache   │ Save for next time
    └──────────┘
```

### 4. Time-To-Live (TTL)

**Default**: 24 hours

After 24 hours, cache expires and PDF is re-extracted.

**Configure TTL**:
```python
# 1 hour cache
extractor = UnifiedExtractor(cache_ttl_hours=1)

# 7 days cache
extractor = UnifiedExtractor(cache_ttl_hours=168)

# Disable caching
extractor = UnifiedExtractor(enable_caching=False)
```

---

## Cache Performance

### Your Test Results

From the test run:

| Metric | Value |
|--------|-------|
| **Total PDFs** | 23 |
| **Cached** | 1 (10k1222-1-20.pdf) |
| **Newly Extracted** | 6 |
| **Cache Hit Time** | 0.01s |
| **Extraction Time** | 60-850s |
| **Speedup** | **60,000x faster!** |

**Example**:
- `10k1222-1-20.pdf`: **0.01s** (cached) vs **826s** (fresh extraction)
- **Savings**: 826 seconds = 13.7 minutes!

---

## Cache Management

### View Cache Stats

```python
from extraction import UnifiedExtractor

extractor = UnifiedExtractor()
stats = extractor.cache.get_stats()

print(stats)
# {
#     'enabled': True,
#     'total_files': 7,
#     'expired_files': 0,
#     'total_size_mb': 3.7,
#     'cache_dir': '.cache/extraction',
#     'ttl_hours': 24
# }
```

### Clear Cache

```python
# Clear all cache
deleted = extractor.clear_cache()
print(f"Deleted {deleted} cache files")

# Clear expired only
deleted = extractor.cache.cleanup_expired()
print(f"Deleted {deleted} expired files")

# Force re-extraction (ignore cache)
result = extractor.extract("document.pdf", force=True)
```

### Manual Cache Management

```bash
# View cache directory
ls -lh .cache/extraction/

# Check cache size
du -sh .cache/extraction/

# Clear cache manually
rm -rf .cache/extraction/*.pkl

# View cache file
python3 -c "
import pickle
with open('.cache/extraction/cfc9406b3d4038810d1d34d53de1a29c.pkl', 'rb') as f:
    result = pickle.load(f)
    print(f'Tables: {len(result.tables)}')
    print(f'Quality: {result.quality_score}')
"
```

---

## Storage Format

### Pickle Format (.pkl)

Cache files use Python's `pickle` format:

**Advantages**:
- [DONE] Fast serialization/deserialization
- [DONE] Preserves Python objects exactly
- [DONE] Compact binary format

**Disadvantages**:
- [WARNING] Python-specific (not portable to other languages)
- [WARNING] Security risk if loading untrusted files

### File Size

Typical cache file sizes:
- **Small PDF** (few tables): 2-10 KB
- **Medium PDF** (10-50 tables): 100-500 KB
- **Large PDF** (500+ tables): 500 KB - 1 MB

Your largest cache file: **832 KB** (likely a 10-K with ~530 tables)

---

## Cache Invalidation

Cache is automatically invalidated when:

1. **File Modified**: PDF file timestamp changes
2. **TTL Expired**: Cache older than 24 hours (default)
3. **Manual Clear**: `extractor.clear_cache()`
4. **Force Flag**: `extract(pdf, force=True)`

**Example**:
```python
# Original extraction
result1 = extractor.extract("report.pdf")  # Takes 60s, creates cache

# Cached retrieval
result2 = extractor.extract("report.pdf")  # Takes 0.01s, uses cache

# Modify PDF file
# ... edit report.pdf ...

# Cache invalidated automatically
result3 = extractor.extract("report.pdf")  # Takes 60s, new cache created
```

---

## Production Recommendations

### 1. Use Persistent Cache

For production, keep cache enabled:

```python
extractor = UnifiedExtractor(
    enable_caching=True,
    cache_ttl_hours=168  # 7 days for financial reports
)
```

### 2. Monitor Cache Size

```bash
# Add to cron job
du -sh .cache/extraction/ >> cache_size.log
```

### 3. Periodic Cleanup

```python
# Clean expired cache weekly
from extraction import UnifiedExtractor

extractor = UnifiedExtractor()
deleted = extractor.cache.cleanup_expired()
print(f"Cleaned up {deleted} expired cache files")
```

### 4. Backup Cache

```bash
# Backup cache before clearing
tar -czf cache_backup_$(date +%Y%m%d).tar.gz .cache/extraction/
```

---

## Advanced: Redis Cache (Future)

For distributed systems, Redis cache is planned:

```python
from extraction.cache import RedisCache

# Redis cache (shared across servers)
cache = RedisCache(redis_url="redis://localhost:6379")
extractor = UnifiedExtractor(cache=cache)
```

**Benefits**:
- Shared cache across multiple servers
- Faster than file-based cache
- Built-in TTL management
- Automatic memory management

---

## Summary

### Current Setup

[DONE] **Caching Enabled**: Yes  
[DONE] **Cache Location**: `.cache/extraction/`  
[DONE] **Cache Format**: Pickle (.pkl)  
[DONE] **TTL**: 24 hours  
[DONE] **Current Size**: 7 files, 3.7 MB  
[DONE] **Performance**: 60,000x faster for cached files  

### Key Benefits

1. **Speed**: Instant retrieval vs 10+ minutes extraction
2. **Cost**: Saves compute resources
3. **Reliability**: Consistent results
4. **Automatic**: No manual intervention needed

### Best Practices

1. [DONE] Keep caching enabled in production
2. [DONE] Monitor cache size periodically
3. [DONE] Clean expired cache weekly
4. [DONE] Backup cache before major changes
5. [DONE] Use longer TTL for stable documents (7 days)

---

**Cache is your friend!** It's already saving you hours of processing time. 

---

# Enterprise Features
# Enterprise-Grade Extraction System - Complete [DONE]

## Production-Ready Features

### [DONE] Comprehensive Logging
```
.logs/extraction/
├── extraction_20251127.log          # All logs
└── extraction_errors_20251127.log   # Errors only
```

**Features:**
- Structured logging with timestamps
- Separate error log file
- File + console handlers
- Configurable log levels
- Automatic daily rotation

**Usage:**
```python
from extraction.logging_config import get_logger

logger = get_logger(__name__)
logger.info("Extraction started")
logger.error("Extraction failed", exc_info=True)
```

---

### [DONE] Metrics Collection
```
.metrics/extraction/
└── metrics_20251127.jsonl  # Daily metrics
```

**Tracked Metrics:**
- Extraction success/failure rate
- Backend usage statistics
- Average quality scores
- Extraction times
- Tables found per PDF
- Error rates by backend

**Usage:**
```python
from extraction.metrics import get_metrics_collector

metrics = get_metrics_collector()
stats = metrics.get_stats()

print(f"Success rate: {stats['success_rate']:.1f}%")
print(f"Avg quality: {stats['avg_quality_score']:.1f}")
print(f"Total tables: {stats['total_tables']}")
```

---

### [DONE] 4 Extraction Backends

| Backend | Priority | Use Case | Quality | Speed |
|---------|----------|----------|---------|-------|
| **Docling** | 1 | Complex financial tables | 85+ | Medium |
| **PyMuPDF** | 2 | Fast extraction, native detection | 70+ | Fast |
| **pdfplumber** | 3 | 2-column layouts, complex tables | 65+ | Medium |
| **Camelot** | 4 | Grid-based tables, high accuracy | 75+ | Slow |

---

### [DONE] Automatic Fallback Strategy

```
1. Try Docling (quality >= 80?)
   ├─ Yes → Use result [OK]
   └─ No → Try fallback

2. Try PyMuPDF (quality >= 70?)
   ├─ Yes → Use result [OK]
   └─ No → Try fallback

3. Try pdfplumber (quality >= 65?)
   ├─ Yes → Use result [OK]
   └─ No → Try fallback

4. Try Camelot (quality >= 60?)
   ├─ Yes → Use result [OK]
   └─ No → Use best result

5. Return best result from all attempts
```

---

### [DONE] Quality Assessment

**Metrics (0-100 score):**
- Table count (20 points)
- Cell completeness (30 points)
- Structure integrity (25 points)
- Text quality (15 points)
- Backend confidence (10 points)

**Grades:**
- Excellent: 90-100
- Good: 75-89
- Fair: 60-74
- Poor: 0-59

---

### [DONE] Caching System

**Features:**
- File-based cache with TTL
- Automatic cleanup of expired entries
- MD5-based cache keys
- Cache statistics

**Storage:**
```
.cache/extraction/
└── {md5_hash}.pkl  # Cached results
```

---

### [DONE] Error Handling

**Comprehensive error handling:**
- Backend unavailable → Try fallback
- Extraction failed → Log error, try next
- All backends failed → Return best attempt
- Invalid PDF → Clear error message
- Timeout handling → Configurable

---

### [DONE] Monitoring & Observability

**Real-time monitoring:**
```python
extractor = UnifiedExtractor()

# Get system stats
stats = extractor.get_stats()
print(stats)

# Output:
{
  "backends": [...],
  "available_backends": ["docling", "pymupdf", "pdfplumber"],
  "min_quality": 60.0,
  "cache": {
    "enabled": true,
    "total_files": 42,
    "total_size_mb": 15.3,
    "ttl_hours": 24
  }
}
```

**Metrics dashboard:**
```python
from extraction.metrics import get_metrics_collector

metrics = get_metrics_collector()
stats = metrics.get_stats()

# Output:
{
  "total_extractions": 150,
  "successful": 145,
  "failed": 5,
  "success_rate": 96.7,
  "avg_quality_score": 82.3,
  "avg_extraction_time": 28.5,
  "total_tables": 342,
  "backend_stats": {
    "docling": {
      "count": 120,
      "success": 118,
      "success_rate": 98.3,
      "avg_time": 32.1
    },
    "pymupdf": {
      "count": 25,
      "success": 22,
      "success_rate": 88.0,
      "avg_time": 5.2
    },
    ...
  }
}
```

---

## Architecture

### Directory Structure
```
extraction/
├── __init__.py                  # Main exports
├── base.py                      # Interfaces & data classes
├── unified_extractor.py         # Main API
├── strategy.py                  # Fallback logic
├── quality.py                   # Quality assessment
├── cache.py                     # Caching system
├── logging_config.py            # Enterprise logging ✨ NEW
├── metrics.py                   # Metrics collection ✨ NEW
└── backends/
    ├── __init__.py
    ├── docling_backend.py       # Priority 1
    ├── pymupdf_backend.py       # Priority 2
    ├── pdfplumber_backend.py    # Priority 3
    └── camelot_backend.py       # Priority 4 ✨ NEW
```

**Total**: 13 Python modules (~2,500 lines)

---

## Enterprise Features Checklist

### [DONE] Logging
- [x] Structured logging
- [x] File + console handlers
- [x] Error log separation
- [x] Daily rotation
- [x] Configurable levels

### [DONE] Monitoring
- [x] Metrics collection
- [x] Performance tracking
- [x] Success/failure rates
- [x] Backend statistics
- [x] Real-time stats API

### [DONE] Reliability
- [x] Automatic fallback
- [x] Error handling
- [x] Quality assessment
- [x] Retry logic
- [x] Graceful degradation

### [DONE] Performance
- [x] Caching system
- [x] Multiple backends
- [x] Fast fallback
- [x] Optimized extraction
- [x] Resource management

### [DONE] Scalability
- [x] Modular architecture
- [x] Easy to add backends
- [x] Configurable behavior
- [x] Batch processing
- [x] Extensible design

### [DONE] Observability
- [x] Comprehensive logs
- [x] Metrics dashboard
- [x] Cache statistics
- [x] Backend health
- [x] Performance metrics

---

## Production Usage

### Basic
```python
from extraction import UnifiedExtractor

# Initialize with all features
extractor = UnifiedExtractor(
    backends=["docling", "pymupdf", "pdfplumber", "camelot"],
    min_quality=75.0,
    enable_caching=True,
    cache_ttl_hours=24
)

# Extract
result = extractor.extract("document.pdf")

# Check logs
# .logs/extraction/extraction_20251127.log

# Check metrics
# .metrics/extraction/metrics_20251127.jsonl
```

### Monitoring
```python
from extraction import UnifiedExtractor
from extraction.metrics import get_metrics_collector

extractor = UnifiedExtractor()

# Process batch
for pdf in pdf_files:
    result = extractor.extract(pdf)

# Get metrics
metrics = get_metrics_collector()
stats = metrics.get_stats()

print(f"Success rate: {stats['success_rate']:.1f}%")
print(f"Avg quality: {stats['avg_quality_score']:.1f}")
print(f"Backend usage: {stats['backend_stats']}")
```

### Production Deployment
```python
import logging
from extraction import UnifiedExtractor
from extraction.logging_config import ExtractionLogger

# Configure logging
ExtractionLogger()  # Auto-configures

# Create extractor
extractor = UnifiedExtractor(
    backends=["docling", "pymupdf"],  # Production backends
    min_quality=80.0,                  # Higher threshold
    enable_caching=True,
    cache_ttl_hours=48
)

# Process with monitoring
try:
    result = extractor.extract(pdf_path)
    
    if result.quality_score < 80:
        logger.warning(f"Low quality: {result.quality_score:.1f}")
    
except Exception as e:
    logger.error(f"Extraction failed: {e}", exc_info=True)
    # Handle error
```

---

## Comparison: Before vs After

| Feature | Before | After |
|---------|--------|-------|
| **Backends** | 1 (Docling) | 4 (Docling, PyMuPDF, pdfplumber, Camelot) |
| **Logging** | Basic print() | Enterprise logging system |
| **Metrics** | None | Comprehensive metrics collection |
| **Monitoring** | None | Real-time stats + dashboard |
| **Error Handling** | Basic try/catch | Comprehensive with fallback |
| **Caching** | None | File-based with TTL |
| **Quality Assessment** | None | 0-100 score with 5 metrics |
| **Observability** | None | Logs + metrics + stats API |
| **Production Ready** | No | Yes [DONE] |

---

## Summary

### [DONE] Enterprise-Grade System

**13 modules, ~2,500 lines of production-ready code**

**Features:**
- [DONE] 4 extraction backends with automatic fallback
- [DONE] Comprehensive logging (.logs/ directory)
- [DONE] Metrics collection (.metrics/ directory)
- [DONE] Quality assessment (0-100 score)
- [DONE] Caching system (.cache/ directory)
- [DONE] Error handling & retry logic
- [DONE] Real-time monitoring & stats
- [DONE] Extensible architecture
- [DONE] Production-ready

**This is now a professional, enterprise-grade extraction system!** 
