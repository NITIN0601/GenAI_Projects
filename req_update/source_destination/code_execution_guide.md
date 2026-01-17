# Code Execution Guide & File List

##  How to Run (Command Line)

Make sure you are in the project root directory.

### 7. Table Time-Series View Generation (Step 7)

**Objective:** Generate Time-Series Views for all tables.

**Command:**
```bash
python3 src/table_view/run_table_view.py
```

**Output:**
- `./data/table_views/Master_Table_Index.csv`
- `./data/table_views/[Table_ID].csv`

---

## 8. Full Pipeline Automation
This runs the complete end-to-end process: Steps 0 through 6 (Resequencing → Wide Export → Normalization → Merge).

```bash
python3 -m src.pipeline.orchestrate_pipeline
```

### 2. Run Steps 1-4 Only (Wide Export)
Runs only the standard CSV export (Extraction, Category Separation, Metadata Injection, Data Formatting).

```bash
python -m src.infrastructure.extraction.exporters.run_csv_export
```

### 2. Run Index Resequencing & Analysis Only
Use this to specifically test the sheet splitting and resequencing logic.

**Analyze a single file (Non-destructive):**
```bash
python3 scripts/test_index_resequencer.py --mode analyze --file data/processed/10q0925_tables.xlsx
```

**Process all files:**
```bash
python3 scripts/test_index_resequencer.py --mode all --dir data/processed
```

### 3. Run Data Normalization (Wide → Long Format)
Transform existing CSV files from wide to long format.

**Normalize a specific workbook:**
```bash
PYTHONPATH=. python3 scripts/normalize_csv_data.py --workbook 10q0925
```

**Normalize all workbooks:**
```bash
PYTHONPATH=. python3 scripts/normalize_csv_data.py --all
```

**Re-export with normalization enabled:**
```bash
PYTHONPATH=. python3 scripts/export_with_normalization.py
```

##  Code File List

### Entry Points & Scripts
| File Path | Purpose |
|-----------|---------|
| `src/pipeline/orchestrate_pipeline.py` | **Main Orchestrator**. Runs Steps 0-6 sequentially. |
| `src/infrastructure/extraction/exporters/run_csv_export.py` | Implementation for Steps 1-4 (Wide Export). |
| `scripts/test_index_resequencer.py` | Script to test and analyze index re-sequencing and sheet splitting. |
| `scripts/normalize_csv_data.py` | CLI tool to normalize CSV files (wide → long). |
| `scripts/export_with_normalization.py` | Re-export with normalization enabled. |
| `scripts/verify_imports.py` | Verifies project import statements. |
| `scripts/audit_imports.py` | Audits project imports for issues. |
| `scripts/download_documents.py` | Utility to download source documents. |

### Core Implementation (`src/`)
| File Path | Purpose |
|-----------|---------|
| `src/index_sheet_resequencer.py` | Core logic for re-sequencing Index sheets and splitting multi-table sheets. |
| `src/infrastructure/extraction/exporters/csv_exporter/exporter.py` | Orchestrates the Excel-to-CSV migration process. |
| `src/infrastructure/extraction/exporters/csv_exporter/category_separator.py` | Detects categories and separates empty/metadata-only tables. |
| `src/infrastructure/extraction/exporters/csv_exporter/metadata_injector.py` | Injects Source, Section, and Table Title columns. |
| `src/infrastructure/extraction/exporters/csv_exporter/data_formatter.py` | Handles currency ($) and percentage (%) formatting. |
| `src/infrastructure/extraction/exporters/csv_exporter/data_normalizer.py` | **Step 6**: Wide→Long transformation (Dates, Header, Data Value). |
| `src/infrastructure/extraction/exporters/csv_exporter/metadata_extractor.py` | Extracts metadata blocks from Excel sheets. |
| `src/infrastructure/extraction/exporters/csv_exporter/index_builder.py` | Builds the enhanced Index.csv with consolidated metadata. |

### Tests
| File Path | Purpose |
|-----------|---------|
| `tests/unit/test_category_separator.py` | Unit tests for category logic. |
| `tests/unit/test_metadata_injector.py` | Unit tests for metadata injection. |
| `tests/unit/test_formatter.py` | Unit tests for data formatting. |
| `tests/test_data_normalizer.py` | Unit tests for date column value separation (7 tests). |

##  Pipeline Flow

```
Step 0: Index Re-sequencing     → xlsx processed in-place
Step 1: Excel to CSV Migration  → xlsx → csv files created
Step 2: Category Separation     → adds Category column
Step 3: Metadata Injection      → adds Source, Section, Table Title
Step 4: Data Formatting         → formats values ($, %)
Step 5: Date Column Value Separation → wide → long format
Step 6a: Merge per Source           → [Source]_consolidated.csv
Step 6b: Master Consolidation         → Master_Consolidated.csv
Step 7a: Master Time-Series View Generation -> Master_Time_Series.csv
Step 7b: Table Time-Series View Generation -> [Table_ID].csv
```

##  Data Directories

| Path | Purpose |
|------|---------|
| `data/processed/*.xlsx` | Source xlsx files |
| `data/processed/test_output/` | Re-sequenced xlsx output |
| `data/csv_output/[workbook]/` | Final CSV exports |
