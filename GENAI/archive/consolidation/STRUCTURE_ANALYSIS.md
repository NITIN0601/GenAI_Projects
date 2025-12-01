# Repository Structure Analysis: /extraction vs /scrapers

## Current State

### `/extraction/` - PDF Extraction Backends
**Purpose**: Extract tables from PDFs using different backends

**Contents:**
- `base.py` - Interfaces
- `unified_extractor.py` - Main API
- `strategy.py` - Fallback logic
- `quality.py` - Quality assessment
- `cache.py` - Caching
- `logging_config.py` - Logging
- `metrics.py` - Metrics
- `backends/` - 4 extraction backends (Docling, PyMuPDF, pdfplumber, Camelot)

**Total**: 13 modules

---

### `/scrapers/` - Utility Modules
**Purpose**: Process and normalize extracted data

**Contents:**
1. `metadata_extractor.py` (176 lines) - Extract metadata from filenames/content
2. `label_normalizer.py` (272 lines) - Normalize financial labels across documents
3. `period_parser.py` (unknown) - Parse fiscal periods
4. `unit_converter.py` (unknown) - Convert units (millions, billions)
5. `__init__.py` - Package init

**Total**: 5 modules

---

## Analysis

### Are They Duplicates? **NO!**

| Feature | /extraction | /scrapers |
|---------|-------------|-----------|
| **Purpose** | Extract tables from PDFs | Process extracted data |
| **Function** | PDF → Tables | Tables → Normalized data |
| **Stage** | Extraction | Post-processing |
| **Overlap** | None | None |

### Relationship

```
PDF File
   ↓
/extraction/  ← Extract tables from PDF
   ↓
Raw Tables
   ↓
/scrapers/    ← Normalize labels, extract metadata, parse periods
   ↓
Normalized Data
```

---

## Decision: **KEEP BOTH** ✅

### Rationale

1. **Different Purposes**
   - `/extraction/` = Get data OUT of PDFs
   - `/scrapers/` = PROCESS the extracted data

2. **Complementary**
   - Extraction provides raw tables
   - Scrapers normalize and enrich

3. **No Duplication**
   - Zero overlap in functionality
   - Each has distinct responsibility

---

## Recommended Structure

### Option 1: Keep As-Is (RECOMMENDED) ✅
```
/GENAI/
├── extraction/          # PDF extraction backends
│   ├── backends/
│   └── ...
├── scrapers/            # Data processing utilities
│   ├── metadata_extractor.py
│   ├── label_normalizer.py
│   ├── period_parser.py
│   └── unit_converter.py
└── utils/               # Common utilities
    └── extraction_utils.py
```

**Pros:**
- Clear separation of concerns
- Easy to understand
- Modular

**Cons:**
- None

### Option 2: Merge into /extraction (NOT RECOMMENDED) ❌
```
/GENAI/
└── extraction/
    ├── backends/        # PDF extraction
    ├── processing/      # Data processing (from scrapers/)
    └── ...
```

**Pros:**
- Single directory

**Cons:**
- Confusing (extraction != processing)
- Breaks separation of concerns
- Harder to maintain

---

## Recommendation

### ✅ KEEP CURRENT STRUCTURE

**No changes needed!** The structure is already optimal:

1. `/extraction/` - Handles PDF extraction
2. `/scrapers/` - Handles data processing
3. `/utils/` - Common utilities

This is a **clean, professional structure** with clear separation of concerns.

---

## What Was Already Moved to /unwanted

✅ **Duplicate extraction code** (already moved):
- `extract_page_by_page.py`
- `extract_structure_correct.py`
- `scrapers/docling_scraper.py` (duplicate of extraction/backends/docling_backend.py)
- `scrapers/pdf_scraper.py` (duplicate of extraction/backends/pdfplumber_backend.py)

---

## Final Structure

```
/GENAI/
├── extraction/                    ✅ PDF Extraction (13 modules)
│   ├── backends/
│   │   ├── docling_backend.py
│   │   ├── pymupdf_backend.py
│   │   ├── pdfplumber_backend.py
│   │   └── camelot_backend.py
│   ├── unified_extractor.py
│   ├── strategy.py
│   ├── quality.py
│   ├── cache.py
│   ├── logging_config.py
│   └── metrics.py
│
├── scrapers/                      ✅ Data Processing (5 modules)
│   ├── metadata_extractor.py
│   ├── label_normalizer.py
│   ├── period_parser.py
│   ├── unit_converter.py
│   └── __init__.py
│
├── utils/                         ✅ Common Utilities
│   └── extraction_utils.py
│
└── unwanted/                      ✅ Deprecated Code
    ├── extract_page_by_page.py
    ├── extract_structure_correct.py
    ├── docling_scraper.py
    └── pdf_scraper.py
```

---

## Conclusion

**No action needed!** ✅

The current structure is **already optimized**:
- `/extraction/` - PDF extraction backends
- `/scrapers/` - Data processing utilities
- No duplication
- Clear separation of concerns
- Professional structure

**This is enterprise-grade organization!** 🚀
