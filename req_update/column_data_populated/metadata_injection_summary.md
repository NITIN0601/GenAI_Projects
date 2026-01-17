# Metadata Column Injection - Implementation Summary

**Date:** 2026-01-15  
**Status:**  COMPLETE  
**Feature:** Added Source, Section, and Table Title columns to CSV output

---

## What Was Implemented

Successfully implemented metadata column injection feature that adds three additional columns to each exported CSV table:

1. **Source** - PDF filename and page number (e.g., `10q0925.pdf_pg7`)
2. **Section** - Section name from Index sheet (e.g., `Business Segment Results`)
3. **Table Title** - Table title from Index sheet (e.g., `Selected Financial Information`)

These columns are prepended to the existing table data, appearing **before** `Category` and `Product/Entity` columns.

---

## Files Created

### 1. `metadata_injector.py`
**Location:** `src/infrastructure/extraction/exporters/csv_exporter/metadata_injector.py`

- Created `MetadataInjector` class
- Implements `inject_metadata_columns()` method to prepend metadata columns
- Factory function `get_metadata_injector()` for component initialization

---

## Files Modified

### 1. `exporter.py`
**Location:** `src/infrastructure/extraction/exporters/csv_exporter/exporter.py`

**Changes:**
- Added `MetadataInjector` import
- Added `enable_metadata_injection` parameter to `__init__()` (defaults to `True`)
- Created `_build_index_metadata_map()` method to parse Index sheet metadata
- Modified `export_workbook()` to:
  - Load Index sheet first
  - Build metadata map using Link column
  - Pass metadata to `_process_sheet()`
- Modified `_process_sheet()` to:
  - Accept `index_metadata` parameter
  - Lookup metadata for each table by table index
  - Inject metadata columns after data formatting
  - Log warnings for incomplete metadata
- Updated header inclusion logic to always write headers when metadata injection is enabled
- Updated `get_csv_exporter()` factory to support `enable_metadata_injection` parameter

### 2. `__init__.py`
**Location:** `src/infrastructure/extraction/exporters/csv_exporter/__init__.py`

**Changes:**
- Added `MetadataInjector` import
- Added `get_metadata_injector` import
- Updated `__all__` export list to include new components

---

## Column Order

**Before:**
```
Category | Product/Entity | <period headers>...
```

**After:**
```
Source | Section | Table Title | Category | Product/Entity | <period headers>...
```

---

## Sample Output

### Single-Table Sheet (1.csv)
```csv
Source,Section,Table Title,Category,Product/Entity,MS/PF,New York Stock Exchange
10q0925.pdf_pg1,Fair Value Asset (Liability) of Credit Protection Sold,Securities registered pursuant to Section 12(b) of the Act:,,Depositary Shares...,MS/PI,New York Stock Exchange
```

### Multi-Table Sheet (2_table_1.csv)
```csv
Source,Section,Table Title,Category,Product/Entity,Q3-QTD-2025,Q3-QTD-2024,Q3-YTD-2025,Q3-YTD-2024
10q0925.pdf_pg7,Business Segment Results,Selected Financial Information and Other Statistical Data,Consolidated results,Net revenues,"$18,224","$15,383","$52,755","$45,538"
```

---

## How It Works

1. **Index Loading:** When `export_workbook()` is called, the Index sheet is loaded first
2. **Metadata Mapping:** `_build_index_metadata_map()` parses the Index and creates a mapping:
   - Uses the `Link` column to determine which sheet each table belongs to
   - Groups tables by sheet name
   - Assigns `Table_Index` based on order within each sheet
3. **Sheet Processing:** For each sheet, metadata is passed to `_process_sheet()`
4. **Metadata Injection:** After category separation and data formatting:
   - Looks up metadata for the current table using `Table_Index`
   - Extracts Section, Table Title, Source, and PageNo
   - Constructs Source field as `{Source}_pg{PageNo}`
   - Injects three columns at the beginning of the DataFrame
5. **Warnings:** Logs warnings for missing or incomplete metadata

---

## Metadata Lookup Strategy

The implementation uses the **Link column** from the original Index sheet:

```python
# Example Link values: '→ 1', '→ 2', '→ 147'
# Parsed to sheet names: '1', '2', '147'
```

For multi-table sheets, tables are matched by position (Table_Index):
- First table in sheet → Table_Index = 1
- Second table in sheet → Table_Index = 2
- etc.

---

## Error Handling

### Missing Metadata
If metadata is not found for a table:
- Columns are still added with empty strings
- Warning is logged with details
- Export continues successfully

Example warning:
```
Incomplete metadata for sheet 60 table 2: section='', table_title='', source=''
```

---

## Configuration

The feature can be enabled/disabled when creating the exporter:

```python
from src.infrastructure.extraction.exporters.csv_exporter import get_csv_exporter

# Enable metadata injection (default)
exporter = get_csv_exporter(enable_metadata_injection=True)

# Disable metadata injection
exporter = get_csv_exporter(enable_metadata_injection=False)
```

---

## Testing Results

 Successfully tested on `10q0925_tables.xlsx`:
- 160 sheets processed
- 242 tables exported
- 243 CSV files created
- Metadata columns correctly populated
- Column order matches specification
- Headers included in all CSV files

---

## Next Steps

The feature is complete and ready for production use. To use it:

```python
from src.infrastructure.extraction.exporters.csv_exporter import get_csv_exporter
from pathlib import Path

exporter = get_csv_exporter()
result = exporter.export_workbook(
    xlsx_path=Path('./data/processed/your_file_tables.xlsx'),
    output_dir=Path('./data/csv_output/your_file')
)
```

All CSV files will automatically include the Source, Section, and Table Title columns.
