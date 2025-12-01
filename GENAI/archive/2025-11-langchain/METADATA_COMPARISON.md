# Metadata Comparison: Current vs Enhanced

## Current Metadata (Basic - 6 fields)

```python
{
    "document_id": "d4ecd73cf0cf0a9f86f29b78d49a980d",
    "source_doc": "10k1222-1-20.pdf",
    "page_no": 1,
    "table_title": "Table 1 (Rows 1-10)",
    "year": "2022",
    "report_type": "10-K"
}
```

## Enhanced Metadata (Production-Grade - 21+ fields)

```python
{
    # Document Information
    "source_doc": "10k1222-1-20.pdf",
    "page_no": 1,
    "chunk_reference_id": "550e8400-e29b-41d4-a716-446655440000",
    
    # Company Information
    "company_ticker": "MS",
    "company_name": "Morgan Stanley",
    
    # Financial Statement Context
    "statement_type": "balance_sheet",  # or income_statement, cash_flow, footnotes
    "filing_type": "10-K",
    "fiscal_period_end": "2022-12-31",
    "restatement": false,
    
    # Table Identification
    "table_title": "Consolidated Balance Sheet",
    "table_type": "summary",  # or detail, reconciliation, segment
    "table_index": 1,
    
    # Temporal Information
    "year": 2022,
    "quarter": null,  # For 10-K
    "fiscal_period": "Year Ended December 31, 2022",
    "comparative_periods": ["2022", "2021"],  # Multi-year tables
    
    # Table-Specific Metadata (CRITICAL)
    "units": "millions",  # or thousands, billions
    "currency": "USD",
    "is_consolidated": true,
    
    # Table Structure
    "column_headers": "Assets|December 31, 2022|December 31, 2021",
    "row_headers": "Cash|Securities|Loans|Total Assets",
    "column_count": 3,
    "row_count": 15,
    "table_structure": "multi_header",  # or simple, nested
    
    # Hierarchical Information
    "parent_section": "Assets",
    "subsection": "Current Assets",
    "footnote_references": ["1", "3"],
    "related_tables": ["table_2_id", "table_3_id"],
    
    # Multi-level Headers
    "has_multi_level_headers": true,
    "main_header": "Consolidated Financial Position",
    "sub_headers": "Current Period|Prior Period",
    
    # Content Analysis
    "has_currency": true,
    "currency_count": 45,
    "has_subtotals": true,
    "has_calculations": true,
    
    # Extraction Metadata
    "extraction_date": "2025-11-29T15:30:00Z",
    "extraction_backend": "docling",
    "quality_score": 85.0,
    "extraction_confidence": 0.95,
    
    # Chunk Management
    "chunk_type": "complete",  # or header, data, footer
    "overlapping_context": "Previous rows: ...",
    "table_start_page": 1,
    "table_end_page": 2
}
```

---

## Key Missing Fields

### Critical for Financial Analysis
1. **statement_type** - Balance Sheet, Income Statement, Cash Flow
2. **units** - Thousands, Millions, Billions (CRITICAL for accuracy!)
3. **currency** - USD, EUR, etc.
4. **fiscal_period_end** - Exact date (2022-12-31)
5. **comparative_periods** - Multi-year data

### Important for Context
6. **company_ticker** - MS, AAPL, etc.
7. **company_name** - Morgan Stanley
8. **table_type** - Summary, Detail, Reconciliation
9. **column_headers** - For better understanding
10. **row_headers** - For better understanding

### Useful for Advanced Queries
11. **parent_section** - Assets, Liabilities, etc.
12. **subsection** - Current Assets, Long-term Assets
13. **footnote_references** - Link to footnotes
14. **has_multi_level_headers** - Complex table indicator
15. **has_subtotals** - Contains calculated totals

---

## Impact of Missing Metadata

### Current Limitations
```python
# Query: "What was revenue in millions?"
# Problem: No units field!
# Can't distinguish between $1,000 (thousands) vs $1,000 (millions)
```

### With Enhanced Metadata
```python
# Query: "What was revenue in millions?"
# Filter: units="millions" AND statement_type="income_statement"
# Result: Accurate, filtered results
```

---

## Recommendation

### Immediate (High Priority)
Add these fields to current metadata:
1. **units** - CRITICAL for financial accuracy
2. **currency** - USD, EUR, etc.
3. **statement_type** - Balance Sheet, Income Statement, etc.
4. **fiscal_period_end** - Exact date
5. **company_ticker** - For multi-company support

### Soon (Medium Priority)
6. **column_headers** - Better context
7. **row_headers** - Better context
8. **table_type** - Summary vs Detail
9. **comparative_periods** - Multi-year tables

### Later (Nice-to-have)
10. **parent_section** - Hierarchical context
11. **footnote_references** - Link to notes
12. **has_subtotals** - Structure indicator

---

## Implementation Plan

### Step 1: Update TableMetadata Schema
Add missing fields to `src/models/schemas.py`

### Step 2: Update Extraction
Enhance `PDFMetadataExtractor` to extract:
- Units from table headers
- Statement type from title
- Column/row headers
- Fiscal period

### Step 3: Update main.py
Include all metadata fields when storing

### Step 4: Re-extract Data
Run extraction again to populate enhanced metadata

---

## Example: Before vs After

### Before (Current)
```json
{
  "source_doc": "10k1222-1-20.pdf",
  "page_no": 1,
  "table_title": "Table 1",
  "year": "2022",
  "report_type": "10-K"
}
```

### After (Enhanced)
```json
{
  "source_doc": "10k1222-1-20.pdf",
  "page_no": 1,
  "table_title": "Consolidated Balance Sheet",
  "year": 2022,
  "report_type": "10-K",
  "statement_type": "balance_sheet",
  "units": "millions",
  "currency": "USD",
  "fiscal_period_end": "2022-12-31",
  "company_ticker": "MS",
  "column_headers": "Assets|Dec 31, 2022|Dec 31, 2021",
  "column_count": 3,
  "row_count": 45,
  "has_currency": true,
  "extraction_backend": "docling",
  "quality_score": 85.0
}
```

**Result:** Much more useful for queries and filtering!
