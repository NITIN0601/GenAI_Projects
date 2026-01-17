# Master Table Index Mapping Plan

## 1. Objective
To create a comprehensive **Master Table Index** (`Master_Table_Index.csv`) that acts as a central catalog for all available tables (~160) within the `Master_Consolidated.csv` dataset.

## 2. Index Structure (`Master_Table_Index.csv`)

This file serves as the directory/menu for the generated Table Views.

### Schema
| Column | Description | Example |
|---|---|---|
| **Table_ID** | **(NEW)** Sequential Unique ID | `TBL_001` |
| **source_file** | Aggregated list of **files** (Page # stripped) | `10k2024.pdf, 10q0925.pdf` |
| **Section** | Report section context | `Balance Sheet` |
| **Table Title** | Unique table name | `Assets Table` |
| **Product count** | Number of unique line items | `15` |
| **Years** | Range of years covered | `2024-2025` |
| **Record count** | Total number of data rows | `12` |
| **csvfile** | Filename of the view (mapped to ID) | `TBL_001.csv` |

## 3. Generation Logic

### Frequency
Regenerate automatically whenever `Master_Consolidated.csv` is updated.

### Unique Identifier Logic
1.  **Grouping:** Identify unique tables by the composite key: `(Section, Table Title)`.
2.  **Sorting:** Sort these groups alphabetically (Section -> Title) to ensure deterministic sequencing.
3.  **ID Assignment:** Assign sequential IDs (`TBL_001`, `TBL_002`...) to these sorted groups.

### Column Logic
-   **source_file:**
    -   Extract the `Source` column from the master data.
    -   **Clean:** Remove `_pg.*` suffix (e.g., `10k.pdf_pg10` -> `10k.pdf`).
    -   **Aggregate:** Join unique filenames with commas.
-   **csvfile:**
    -   Format: `[Table_ID].csv`.

## 4. Implementation Snippet

```python
def generate_index_record(group, table_id, filename):
    # 1. Clean Sources for Index (Key requirement: Strip Page #)
    raw_sources = group['Source'].dropna().unique().astype(str)
    clean_sources = sorted(set([re.sub(r'_pg.*', '', s) for s in raw_sources]))
    source_str = ", ".join(clean_sources)
    
    # 2. Metrics
    years = extract_year_range(group['Dates'])
    
    return {
        'Table_ID': table_id,
        'source_file': source_str,
        'Section': group['Section'].iloc[0],
        'Table Title': group['Table Title'].iloc[0],
        'Product count': len(group['Product/Entity'].unique()),
        'Years': years,
        'Record count': len(group), # Rows in the view
        'csvfile': filename
    }
```
