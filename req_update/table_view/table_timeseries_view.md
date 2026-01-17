# Table Time Series View Strategy (Individual CSVs)

> [!IMPORTANT]
> **Constraint:** This generation relies **ONLY** on `Master_Consolidated.csv`.

## 1. Objective
To physically materialize distinct time-series CSV files for every unique table. These files act as the data source for any "View" or "Export" requested by the user.

## 2. File Naming Convention
*   **Filename:** `[Table_ID].csv` (e.g., `TBL_001.csv`)
*   **Mapping:** The mapping between `Table_ID` and the human-readable `Table Title` is maintained in `Master_Table_Index.csv` (see `master_table_index_plan.md`).

## 3. CSV Structure (Transposed Matrix)

Each file contains the data for **one specific table**, transformed into a wide format for easy reading.

### Schema
| Source | Dates | Header | [Product 1] | [Product 2] | ... |
|---|---|---|---|---|---|
| *Row Ref* | *Time* | *Context* | *Value* | *Value* | ... |

### Column Definitions
*   **Source:** The definitive source reference for the row.
    *   *Note:* Unlike the Index, this **intentionally includes page numbers** (e.g., `10k.pdf_pg10`) to allow precise data verification.
    *   *Multiple Sources:* If data is aggregated, shows comma-separated values (e.g., `10k.pdf_pg10, 10q.pdf_pg5`).
*   **Dates:** The time period (e.g., `2024`, `Q1-2025`).
*   **Header:** Additional context tag (e.g., `IS`, `WM`).
*   **[Product Columns]:** Dynamic columns generated from the data.
    *   Key: `Category - Product/Entity` (or just `Product/Entity` if Category is null).

## 4. Example Content

**File:** `TBL_001.csv` (Assets Table)

| Source | Dates | Header | Assets - Cash | Assets - Inventory |
|---|---|---|---|---|
| 10k2024.pdf_pg10 | 2024 | IS | 500 | 200 |
| 10q0125.pdf_pg31, 10q0225.pdf_pg33 | Q1-2025 | IS | 550 | 210 |

## 5. Generation Logic

1.  **Input:** `Master_Consolidated.csv`.
2.  **Filter:** Select rows matching the specific `Table Title` (and `Section`) for this ID.
3.  **Pivot:**
    *   **Index:** `Source`, `Dates`, `Header`
    *   **Columns:** `Category - Product/Entity`
    *   **Values:** `Data Value`
4.  **Save:** Write to `data/table_views/TBL_xxx.csv`.
