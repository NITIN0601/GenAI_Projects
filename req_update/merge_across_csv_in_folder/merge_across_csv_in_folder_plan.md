# Merge Across CSV Implementation Plan

## Overview
This plan outlines the process of merging the already normalized individual CSV files into consolidated datasets. 
Since the input files in `data/csv_output_normalized/` are already in the target long format with all metadata columns, the process is a direct concatenation.

**Target Schema (Already present in inputs):**
`| Source | Section | Table Title | Category | Product/Entity | Dates | Header | Data Value |`

## Prerequisites
- **Input Data:**
  - Folders containing normalized CSVs: `./data/csv_output_normalized/[SourceUnit]/` (e.g., `10q0925`).
  - Input CSVs are already normalized and contain all required metadata columns.
- **Tools:**
  - `pandas` for efficient concatenation.

## Detailed Plan

### Step 1: Merge Individual Folder (Per Source Unit)
**Goal:** Create a single consolidated CSV for each source directory (e.g., `10q0925`).

**Workflow:**
1.  **Identify Schema:** Validate that the input files match the expected schema:
    `Source, Section, Table Title, Category, Product/Entity, Dates, Header, Data Value`
2.  **Iterate Folders:** For each subdirectory in `data/csv_output_normalized/`:
    -   **Collect Files:** Glob all `*.csv` files in the folder.
        -   *Exclude* `Index.csv` if present.
        -   *Exclude* any existing consolidated files (e.g., `*_consolidated.csv`).
    -   **Batch Read:** Read all CSVs into a list of DataFrames.
        -   **Encoding:** Use `encoding='utf-8-sig'` to handle BOM artifacts found in source files.
        -   **Empty Check:** Skip files that are empty or contain only a header row.
    -   **Concatenate:** `pd.concat(dfs, ignore_index=True)`
    -   **Export:** Save as `[SourceDirectoryName]_consolidated.csv` in the same folder (or a specific `consolidated` output folder).

### Step 2: Merge Into Master Consolidated CSV
**Goal:** Merge the consolidated files from Step 1 into one final dataset.

**Workflow:**
1.  **Identify Inputs:** List all `*_consolidated.csv` files generated in Step 1.
2.  **Concatenate:** Load and merge into a single DataFrame.
3.  **Consolidate Rows (Deduplication):**
    -   **Condition:** If rows are identical in all columns *except* `Source`, merge them into a single row.
    -   **Grouping Columns:** `Section`, `Table Title`, `Category`, `Product/Entity`, `Dates`, `Header`, `Data Value`.
    -   **Aggregation:** Concatenate unique `Source` values with a comma separator (e.g., `10q0325.pdf_pg48, 10q0925.pdf_pg51`).
    -   **Example:**
        -   *Input:*
            -   `Source A | Val 1`
            -   `Source B | Val 1`
        -   *Output:*
            -   `Source A, Source B | Val 1`
4.  **Export:** Save as `Master_Consolidated.csv`.

## Verification Plan
### Automated Tests
-   **Test Script:** `tests/test_merge_simple.py`
    -   Create a temporary directory with 2 mock normalized CSVs.
    -   Run the merge function.
    -   Assert output row count == sum of input row counts.
    -   Assert output columns match input columns.

### Handling Edge Cases
-   **Byte Order Mark (BOM):** Source files contain `\ufeff` at the start. The script MUST use `encoding='utf-8-sig'` when reading CSVs to prevent header corruption (e.g., `\ufeffSource` vs `Source`).
-   **Empty Files:** Although no 0-byte files were found, the script checks for and skips any files with no data rows to prevent errors.
-   **Index.csv Exclusion:** Crucial to exclude strictly to avoid schema mismatch errors.
-   **Data Types:** `Data Value` column is preserved as object/string to handle mixed numeric and text values without conversion errors.

### Manual Verification
-   Run the script on `data/csv_output_normalized/`.
-   Open `10q0925_consolidated.csv`.
-   Check row count vs sum of individual files (using `wc -l`).
-   Verify that `Source` column contains `10q0925...` entries.

## Implementation Steps
- [x] Create `src/pipeline/merge_csv_pipeline.py`.
- [x] Implement `merge_normalized_folders(base_path)`:
    -   Iterates folders.
    -   Reads and concatenates CSVs.
    -   Saves consolidated outputs.
- [x] Implement `create_master_consolidated(consolidated_files, output_path)`.
- [x] Add row consolidation/deduplication logic to master merge (merge identical rows, concatenate Source).
- [x] Add CLI entry point.
