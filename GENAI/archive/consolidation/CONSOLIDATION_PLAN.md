# Extraction Code Consolidation Analysis

## Current State

### Extraction Files Found (Active)

1. **extraction/** (NEW - Unified System) ✅
   - `extraction/backends/docling_backend.py` - Unified Docling backend
   - `extraction/backends/pymupdf_backend.py` - PyMuPDF backend
   - `extraction/unified_extractor.py` - Main interface
   - `extraction/strategy.py` - Fallback logic
   - `extraction/quality.py` - Quality assessment
   - `extraction/cache.py` - Caching

2. **extract_page_by_page.py** (OLD - 556 lines) ⚠️ DUPLICATE
   - Page-by-page extraction with Docling
   - **DUPLICATE** of extraction/backends/docling_backend.py
   - **ACTION**: Deprecate, update to use unified system

3. **extract_structure_correct.py** (OLD - 201 lines) ⚠️ DUPLICATE
   - Alternative Docling extraction
   - **DUPLICATE** functionality
   - **ACTION**: Move to unwanted/

4. **scrapers/docling_scraper.py** (894 lines) ⚠️ DUPLICATE
   - Advanced Docling scraper
   - **DUPLICATE** of extraction backends
   - **ACTION**: Keep for now (used by production_pipeline.py), mark deprecated

5. **scrapers/pdf_scraper.py** (17KB) ⚠️ DUPLICATE
   - General PDF scraping
   - **DUPLICATE** functionality
   - **ACTION**: Evaluate usage, potentially deprecate

6. **utils/extraction_utils.py** (NEW) ✅
   - Common utilities (DoclingHelper, PDFMetadataExtractor)
   - **KEEP**: Used by unified system

### Files Using Extraction

- `main.py` - Uses old extraction
- `production_pipeline.py` - Uses scrapers/docling_scraper.py
- Tests - Mix of old and new

---

## Consolidation Plan

### Phase 1: Deprecate Old Extraction Files ✅

**Files to deprecate:**
1. `extract_page_by_page.py` → Replace with unified system
2. `extract_structure_correct.py` → Move to unwanted/

**Actions:**
- Add deprecation warnings
- Update to use unified system internally
- Keep for backward compatibility (temporary)

### Phase 2: Update Main Entry Points

**Files to update:**
1. `main.py` - Use unified extractor
2. `production_pipeline.py` - Use unified extractor

### Phase 3: Consolidate Scrapers

**Decision on scrapers/:**
- `docling_scraper.py` - Mark deprecated, point to extraction/
- `pdf_scraper.py` - Evaluate usage, potentially deprecate
- Keep other scrapers (metadata_extractor, label_normalizer, etc.)

### Phase 4: Update Tests

- Update tests to use unified system
- Remove tests for deprecated files

---

## Implementation

### 1. Deprecate extract_page_by_page.py

Add deprecation warning and wrapper to unified system.

### 2. Move extract_structure_correct.py

Move to unwanted/ directory.

### 3. Update main.py

Replace old extraction with unified system.

### 4. Update production_pipeline.py

Replace scraper with unified system.

### 5. Add Migration Guide

Document how to migrate from old to new system.
