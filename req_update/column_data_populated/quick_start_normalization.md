# Date Column Value Separation - Quick Start Guide

This guide shows you how to use the data normalization feature to transform CSV data from wide to long format.

---

## What Does It Do?

Transforms CSV data from **wide format** (period columns) to **long format** (Dates, Header, Data Value):

**Before (Wide)**:
```
Product/Entity    Q3-2025    Q3-2025 IS    Q3-2025 WM
Net revenues      $18,224    $5,000        $3,500
```

**After (Long)**:
```
Product/Entity    Dates      Header    Data Value
Net revenues      Q3-2025              $18,224
Net revenues      Q3-2025    IS        $5,000
Net revenues      Q3-2025    WM        $3,500
```

---

## Option 1: Export with Normalization (Recommended)

Re-export Excel files with normalization enabled from the start:

```bash
cd /Users/nitin/Desktop/Chatbot/Morgan/
python3 scripts/export_with_normalization.py
```

**Output**: `./data/csv_output_normalized/`

---

## Option 2: Normalize Existing CSV Files

Normalize CSV files that have already been exported:

### Normalize a specific workbook:
```bash
cd /Users/nitin/Desktop/Chatbot/Morgan/
python3 scripts/normalize_csv_data.py --workbook 10q0925
```

### Normalize all workbooks:
```bash
cd /Users/nitin/Desktop/Chatbot/Morgan/
python3 scripts/normalize_csv_data.py --all
```

**Note**: This modifies files in-place in `./data/csv_output/`

---

## Option 3: Programmatic Usage

Use in your own Python code:

```python
from src.infrastructure.extraction.exporters.csv_exporter import get_csv_exporter

# Create exporter with normalization enabled
exporter = get_csv_exporter(
    enable_data_normalization=True
)

# Export all workbooks
summary = exporter.export_all()
```

---

## Testing

Run the test suite to verify everything works:

```bash
cd /Users/nitin/Desktop/Chatbot/Morgan/
PYTHONPATH=/Users/nitin/Desktop/Chatbot/Morgan/ python3 tests/test_data_normalizer.py
```

**Expected**: All 7 tests pass 

---

## What Gets Normalized?

###  Period Columns
- `Q1-2025`, `Q2-2025`, `Q3-2025`, `Q4-2025`
- `Q3-QTD-2025`, `Q3-YTD-2025`
- `YTD-2024`
- Period columns with suffixes: `Q3-2025 IS`, `Q3-2025 WM`

###  Excluded Columns
- Fixed metadata columns: `Source`, `Section`, `Table Title`, `Category`, `Product/Entity`
- Unit indicators: `$ in millions`, `in millions`, etc.

---

## Column Mapping

| Original Column | New Columns |
|-----------------|-------------|
| `Q3-QTD-2025` | Dates: `Q3-QTD-2025`, Header: ``, Data Value: (cell value) |
| `Q3-2025 IS` | Dates: `Q3-2025`, Header: `IS`, Data Value: (cell value) |
| `Q3-2025 WM` | Dates: `Q3-2025`, Header: `WM`, Data Value: (cell value) |

---

## Expected Results

### Row Count
- **Formula**: Original rows × Number of period columns
- **Example**: 10 rows × 4 period columns = 40 normalized rows

### Columns
Fixed columns + 3 new columns:
- `Source`, `Section`, `Table Title`, `Category`, `Product/Entity` (fixed)
- `Dates`, `Header`, `Data Value` (new)

---

## Troubleshooting

### "No module named 'src'" Error
Make sure to set PYTHONPATH:
```bash
PYTHONPATH=/Users/nitin/Desktop/Chatbot/Morgan/ python3 [script]
```

### Empty Output
- Check that input CSV files have period columns
- Verify files exist in the expected directory

### Incorrect Parsing
- Review the period patterns in the plan document
- Check the test cases to see expected behavior

---

## Documentation

- **Plan**: `./req_update/column_data_populated/date_column_value_separation_plan.md`
- **Implementation**: `./req_update/column_data_populated/date_column_value_separation_implementation.md`
- **This Guide**: `./req_update/column_data_populated/quick_start_normalization.md`

---

## Need Help?

1. Check the test suite for examples: `./tests/test_data_normalizer.py`
2. Review the implementation summary: `./date_column_value_separation_implementation.md`
3. Look at the core module: `./src/infrastructure/extraction/exporters/csv_exporter/data_normalizer.py`
