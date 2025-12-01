# Usage Guide: /extraction vs /scrapers

> [!TIP]
> **Quick Reference**: `/extraction/` extracts tables from PDFs → `/scrapers/` processes and normalizes the extracted data

## Quick Answer

**`/extraction`** → Use when you need to **GET tables OUT of PDFs**  
**`/scrapers`** → Use when you need to **PROCESS the extracted data**

**The Pipeline**: `PDF → /extraction/ → Raw Tables → /scrapers/ → Normalized Data`

---

## Complete Pipeline Flow

```
┌─────────────────────────────────────────────────────────────┐
│                     PDF DOCUMENT                             │
│                  (10k1224.pdf, 10q0625.pdf)                 │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                  1. EXTRACTION PHASE                         │
│                  Uses: /extraction/                          │
│                                                              │
│  from extraction import UnifiedExtractor                     │
│                                                              │
│  extractor = UnifiedExtractor()                             │
│  result = extractor.extract("10k1224.pdf")                  │
│                                                              │
│  Output: Raw tables in markdown format                      │
│  ┌────────────────────────────────────┐                    │
│  │ | Assets | 2024 | 2023 |          │                    │
│  │ |--------|------|------|          │                    │
│  │ | Cash   | 100  | 90   |          │                    │
│  │ | Loans  | 500  | 450  |          │                    │
│  └────────────────────────────────────┘                    │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                  2. PROCESSING PHASE                         │
│                  Uses: /scrapers/                            │
│                                                              │
│  A. Extract Metadata                                         │
│     from scrapers.metadata_extractor import MetadataExtractor│
│                                                              │
│     extractor = MetadataExtractor("10k1224.pdf")            │
│     metadata = extractor.extract_metadata(                  │
│         table_title="Balance Sheet",                        │
│         page_no=5                                           │
│     )                                                        │
│     # Output: year=2024, quarter=None, report_type="10-K"  │
│                                                              │
│  B. Normalize Labels                                         │
│     from scrapers.label_normalizer import get_label_normalizer│
│                                                              │
│     normalizer = get_label_normalizer()                     │
│     canonical, confidence = normalizer.canonicalize("Cash") │
│     # Output: ("cash_and_equivalents", 0.95)               │
│                                                              │
│  C. Parse Periods                                            │
│     from scrapers.period_parser import parse_period         │
│     # Parse "June 30, 2024" → structured date              │
│                                                              │
│  D. Convert Units                                            │
│     from scrapers.unit_converter import convert_units       │
│     # Convert "100 millions" → 100000000                   │
│                                                              │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                  3. FINAL OUTPUT                             │
│                  Normalized, Enriched Data                   │
│                                                              │
│  {                                                           │
│    "table": "Balance Sheet",                                │
│    "year": 2024,                                            │
│    "report_type": "10-K",                                   │
│    "rows": [                                                │
│      {                                                       │
│        "label": "cash_and_equivalents",  ← Normalized       │
│        "value_2024": 100000000,          ← Converted        │
│        "value_2023": 90000000                               │
│      },                                                      │
│      {                                                       │
│        "label": "loans",                 ← Normalized       │
│        "value_2024": 500000000,          ← Converted        │
│        "value_2023": 450000000                              │
│      }                                                       │
│    ]                                                         │
│  }                                                           │
└─────────────────────────────────────────────────────────────┘
```

---

## Real-World Usage Examples

### Example 1: Basic Extraction Only

**When**: You just need raw tables from PDFs

```python
from extraction import UnifiedExtractor

# Extract tables
extractor = UnifiedExtractor()
result = extractor.extract("10k1224.pdf")

# Use raw tables
for table in result.tables:
    print(table['content'])  # Raw markdown table
```

**Uses**: `/extraction/` only [DONE]

---

### Example 2: Full Pipeline (Extraction + Processing)

**When**: You need normalized, enriched data for analysis

```python
from extraction import UnifiedExtractor
from scrapers.metadata_extractor import MetadataExtractor
from scrapers.label_normalizer import get_label_normalizer

# Step 1: Extract tables
extractor = UnifiedExtractor()
result = extractor.extract("10k1224.pdf")

# Step 2: Process each table
metadata_extractor = MetadataExtractor("10k1224.pdf")
normalizer = get_label_normalizer()

for table in result.tables:
    # Extract metadata
    metadata = metadata_extractor.extract_metadata(
        table_title=table['metadata']['table_title'],
        page_no=table['metadata']['page_no']
    )
    
    # Normalize labels
    # ... process table rows with normalizer
```

**Uses**: `/extraction/` + `/scrapers/` [DONE]

---

### Example 3: Production Pipeline (main.py, production_pipeline.py)

**When**: Processing PDFs for vector database storage

```python
from extraction import UnifiedExtractor
from scrapers.metadata_extractor import MetadataExtractor
from embeddings.vector_store import get_vector_store

# Extract
extractor = UnifiedExtractor()
result = extractor.extract(pdf_path)

# Process & enrich
metadata_extractor = MetadataExtractor(pdf_path)
for table in result.tables:
    # Add metadata
    metadata = metadata_extractor.extract_metadata(
        table['metadata']['table_title'],
        table['metadata']['page_no']
    )
    
    # Store in vector DB
    vector_store.add(table, metadata)
```

**Uses**: `/extraction/` + `/scrapers/` + other components [DONE]

---

## Decision Tree

```
Do you have a PDF?
    │
    ├─ YES → Use /extraction/ to get tables
    │         │
    │         └─ Do you need to normalize/enrich the data?
    │             │
    │             ├─ YES → Use /scrapers/ to process
    │             └─ NO  → Done! Use raw tables
    │
    └─ NO  → Do you have extracted data to process?
              │
              ├─ YES → Use /scrapers/ only
              └─ NO  → Start with /extraction/
```

---

## Module Reference

### `/extraction/` Modules

| Module | Purpose | When to Use |
|--------|---------|-------------|
| `unified_extractor.py` | Main API | Always (entry point) |
| `backends/docling_backend.py` | Docling extraction | Automatic (via strategy) |
| `backends/pymupdf_backend.py` | PyMuPDF extraction | Automatic (fallback) |
| `backends/pdfplumber_backend.py` | pdfplumber extraction | Automatic (fallback) |
| `backends/camelot_backend.py` | Camelot extraction | Automatic (fallback) |
| `strategy.py` | Fallback logic | Automatic (internal) |
| `quality.py` | Quality assessment | Automatic (internal) |
| `cache.py` | Caching | Automatic (if enabled) |
| `logging_config.py` | Logging | Automatic (internal) |
| `metrics.py` | Metrics | Automatic (internal) |

### `/scrapers/` Modules

| Module | Purpose | When to Use |
|--------|---------|-------------|
| `metadata_extractor.py` | Extract year, quarter, report type | After extraction, need metadata |
| `label_normalizer.py` | Normalize financial labels | After extraction, need consistent labels |
| `period_parser.py` | Parse fiscal periods | After extraction, need date parsing |
| `unit_converter.py` | Convert units (M, B, K) | After extraction, need numeric conversion |

---

## Current Usage in Codebase

### `main.py`
```python
# Uses /extraction/ for PDF extraction
from extraction import UnifiedExtractor

extractor = UnifiedExtractor()
result = extractor.extract(pdf_path)
```

### `production_pipeline.py`
```python
# Uses /extraction/ for extraction
from extraction import UnifiedExtractor

# Could use /scrapers/ for processing (not yet integrated)
# TODO: Add metadata extraction and label normalization
```

---

## Summary

| Aspect | /extraction | /scrapers |
|--------|-------------|-----------|
| **Input** | PDF files | Extracted tables |
| **Output** | Raw tables (markdown) | Normalized data |
| **When** | First step (get data) | Second step (process data) |
| **Required** | Always (to get tables) | Optional (for enrichment) |
| **Standalone** | Yes | Yes (if you have extracted data) |
| **Typical Flow** | PDF → Tables | Tables → Normalized |

**Both are independent but work together in a pipeline!** 
