# Table Consolidation Feature

## Overview
Consolidate tables with the same title across multiple quarters/years and export to CSV/Excel for anomaly detection analysis.

---

## Table Matching Logic (Strict Signature Matching)

Tables are merged **only if they have identical structure**. This prevents accidentally combining different tables that share similar names.

### Composite Key

Each table is identified by a three-part key:

```
{Section}::{Normalized Title}::{Row Signature}
```

| Component | Description | Example |
|-----------|-------------|---------|
| **Section** | Business segment | `Institutional Securities` |
| **Normalized Title** | Cleaned, lowercase title | `income statement info` |
| **Row Signature** | Pipe-separated row labels | `net revenues\|compensation\|total expenses` |

### How It Works

1. **Extract Section**: From document metadata (e.g., "Institutional Securities", "Wealth Management")
2. **Normalize Title**: Remove row ranges, clean whitespace, lowercase
3. **Build Row Signature**: Collect all first-column values (row labels), normalize, join with `|`

### Matching Examples

**Tables WILL Merge** (same key):
```
Q1: Inst Securities::balance sheet::assets|liabilities|equity
Q2: Inst Securities::balance sheet::assets|liabilities|equity
```

**Tables WON'T Merge** (different key):
```
Q1: Inst Securities::balance sheet::assets|liabilities|equity
Q2: Wealth Management::balance sheet::assets|liabilities|equity  ← Different section
```

> [!NOTE]
> This strict matching ensures data integrity - tables with even slight row differences are kept separate to prevent incorrect data merging.

---

## Features

### [DONE] Horizontal Table Merging
- **Same rows**: Row headers are preserved
- **Additional columns**: One column set per quarter
- **Different row headers**: Added as new rows (not merged)
- **Missing data**: Filled with "N/A"

### [DONE] Dual Export
- **CSV**: Always exported
- **Excel**: Exported if `EXPORT_BOTH_FORMATS=True`
- **Filename format**: `tablename_yr_month`
  - Example: `contractual_principals_2023-2024_2025_11.csv`

### [DONE] Anomaly Detection Ready
- Clean tabular format
- Consistent column naming
- N/A for missing values
- Both formats for different tools

---

## Configuration

### .env Settings
```bash
# Directory for exported tables
OUTPUT_DIR=outputs/tables

# Export both CSV and Excel
EXPORT_BOTH_FORMATS=True

# Similarity threshold for table matching (0.0-1.0)
TABLE_SIMILARITY_THRESHOLD=0.85
```

---

## Usage

### CLI Command
```bash
# Basic usage
python main.py consolidate "Contractual principals and fair value"

# Custom output directory
python main.py consolidate "Balance Sheet" --output /path/to/output

# Adjust similarity threshold
python main.py consolidate "Revenue" --threshold 0.9
```

### Example Output
```
🔍 Consolidating Tables: 'Contractual principals and fair value'

[OK] Found 4 matching tables

┌─────────┬──────┬─────────────────────────────┬───────┐
│ Quarter │ Year │ Title                       │ Score │
├─────────┼──────┼─────────────────────────────┼───────┤
│ Q1      │ 2024 │ Contractual Principals...   │ 0.95  │
│ Q2      │ 2024 │ Contractual Principals...   │ 0.94  │
│ Q3      │ 2024 │ Contractual Principals...   │ 0.95  │
│ Q4      │ 2023 │ Contractual Principals...   │ 0.93  │
└─────────┴──────┴─────────────────────────────┴───────┘

[OK] Consolidated: 15 rows x 5 columns
Quarters included: Q1 2024, Q2 2024, Q3 2024, Q4 2023

[OK] Export Complete!
  📄 CSV: outputs/tables/contractual_principals_2023-2024_2025_11.csv
  📊 Excel: outputs/tables/contractual_principals_2023-2024_2025_11.xlsx

Preview (first 10 rows):
┌──────────────────────┬─────────────┬─────────────┬─────────────┬─────────────┐
│ Row Header           │ Amount (Q1) │ Amount (Q2) │ Amount (Q3) │ Amount (Q4) │
├──────────────────────┼─────────────┼─────────────┼─────────────┼─────────────┤
│ Loans & receivables  │ $ 1,234M    │ $ 1,456M    │ $ 1,567M    │ $ 1,123M    │
│ Nonaccrual loans     │ $ 234M      │ $ 245M      │ $ 256M      │ $ 223M      │
│ Total                │ $ 1,468M    │ $ 1,701M    │ $ 1,823M    │ $ 1,346M    │
└──────────────────────┴─────────────┴─────────────┴─────────────┴─────────────┘

Tip: These files are ready for anomaly detection analysis
```

---

## Programmatic Usage

```python
from src.rag.table_consolidator import get_table_consolidator
from src.vector_store.stores.faiss_store import get_faiss_store
from src.embeddings.manager import get_embedding_manager

# Initialize
vector_store = get_faiss_store()
embedding_manager = get_embedding_manager()
consolidator = get_table_consolidator(vector_store, embedding_manager)

# Find tables
tables = consolidator.find_tables_by_title("Balance Sheet", top_k=50)

# Consolidate
df, metadata = consolidator.consolidate_tables(tables, table_name="Balance Sheet")

# Export
export_paths = consolidator.export(df, "Balance Sheet", "2023-2024")

print(f"CSV: {export_paths['csv']}")
print(f"Excel: {export_paths['excel']}")
```

---

## Table Merging Logic

### Input Tables

**Q1 2024**:
```
| Row Header           | Amount |
|----------------------|--------|
| Loans & receivables  | 1,234  |
| Nonaccrual loans     | 234    |
```

**Q2 2024**:
```
| Row Header           | Amount |
|----------------------|--------|
| Loans & receivables  | 1,456  |
| Nonaccrual loans     | 245    |
| New Item             | 100    |  ← New row
```

### Consolidated Output

```
| Row Header           | Amount (Q1 2024) | Amount (Q2 2024) |
|----------------------|------------------|------------------|
| Loans & receivables  | 1,234            | 1,456            |
| Nonaccrual loans     | 234              | 245              |
| New Item             | N/A              | 100              | ← N/A for missing
```

---

## Key Benefits

1. **Temporal Analysis**: See how values change across quarters
2. **Anomaly Detection**: Export format ready for ML models
3. **Dual Format**: CSV for Python/R, Excel for manual review
4. **Flexible Search**: High recall with semantic + fuzzy matching
5. **Robust Handling**: N/A for missing data, preserves all row headers

---

## Troubleshooting

### No Tables Found
- Lower similarity threshold: `--threshold 0.8`
- Try broader query: "Fair Value" instead of full title
- Check if tables exist in vector DB: `python main.py stats`

### Wrong Tables Retrieved
- Increase similarity threshold: `--threshold 0.95`
- Use exact table title from PDF
- Check table titles in vector DB metadata

### Missing Columns
- Verify all PDFs are extracted: `python main.py extract`
- Check year/quarter metadata in tables
- Some quarters may genuinely not have the table

---

## Next Steps (Anomaly Detection Project)

These exported files are designed for:
- **Time-series analysis**: Detect unusual value changes
- **Outlier detection**: Identify anomalies across quarters
- **Trend analysis**: Visualize patterns over time
- **Compliance checking**: Verify expected values

Recommended tools:
- Python: pandas, scikit-learn, statsmodels
- R: forecast, anomalize
- Excel: Power Query, conditional formatting

---

**Last Updated**: 2025-12-18  
**Feature Status**: [DONE] Complete & Tested
