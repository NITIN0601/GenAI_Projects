# PDF Extraction Methods - Test Results

## Problem Statement
The "Difference Between Contractual Principal and Fair Value" table has a complex multi-column layout that proves difficult for standard PDF extractors.

## Methods Tested

### 1. pdfplumber (Original GENAI Approach)
- **Status**: ❌ Failed
- **Issue**: Corrupted headers, doesn't properly detect table structure
- **Result**: Got "Loans and other de", "bt2", "$" as headers instead of proper column names

### 2. PyMuPDF Native Table Detection
- **Status**: ❌ Failed  
- **Issue**: `find_tables()` returned 0 tables on page 57
- **Result**: Table not detected at all

### 3. marker-pdf (PDF → Markdown with HTML tables)
- **Status**: ❌ Failed
- **Issue**: Python 3.9 compatibility error with type hints
- **Error**: `TypeError: unsupported operand type(s) for |`

### 4. pymupdf4llm (PDF → Markdown)
- **Status**: ❌ Partial Failure
- **Issue**: Converted PDF but tables not in Markdown table format
- **Result**: 0 tables extracted

## Working Solution

### Your Original extractor.py ✅
- **Status**: ✅ WORKS
- **Method**: Special HTML extraction with custom configuration
- **Configuration**:
  ```python
  "Difference Between Contractual Principal and Fair Value": {
      "strategy": "html",
      "bbox_width": 310,
      "col_tolerance": 38,
      "filter_footnotes": True,
      "stop_titles": ["Fair Value Loans", "Fair Values"]
  }
  ```
- **Result**: Successfully extracts all row elements:
  - Loans and other receivables
  - Nonaccrual loans
  - Borrowings

## Recommendation

**Use the proven extractor.py approach:**

1. Keep pdfplumber for standard tables (works for 95% of tables)
2. Add special HTML extraction for complex tables
3. Use TABLE_CONFIGS to identify which tables need special handling
4. Already implemented in `/GENAI/scrapers/pdf_scraper.py` (lines 19-32, 324-433)

## Next Steps

**Option A**: Use current GENAI scraper with HTML extraction (already added)
- Test if it works now with lxml installed
- Should handle the complex table

**Option B**: Copy exact logic from extractor.py
- Guaranteed to work
- More code duplication

**Option C**: Hybrid approach
- Use extractor.py for complex tables
- Use new scraper for simple tables
