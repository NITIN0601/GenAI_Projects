# Step 5: Date Column Value Separation - Implementation Summary

> **Phase**: Data Normalization (Wide → Long Format)  
> **Status**:  Implemented  
> **Prerequisite**: Steps 1-4 (Excel to CSV, Category Separation, Metadata Injection, Data Formatting)

---

## Overview

Successfully implemented data normalization to transform CSV data from **wide format** to **long format**, unpivoting period header columns into three new columns: `Dates`, `Header`, and `Data Value`.

---

## Implementation Details

### 1. Core Module: `data_normalizer.py`

**Location**: `./src/infrastructure/extraction/exporters/csv_exporter/data_normalizer.py`

**Key Components**:

#### `DataNormalizer` Class
- **Purpose**: Transforms DataFrames from wide to long format
- **Key Features**:
  - Period header parsing with regex pattern matching
  - Unit indicator exclusion (e.g., `$ in millions`)
  - Fixed column preservation
  - Validation of transformation correctness

#### Period Pattern Detection
Supports the following period patterns:
- `Q1-2025`, `Q2-2025`, `Q3-2025`, `Q4-2025`
- `Q1-QTD-2025`, `Q2-QTD-2025`, etc.
- `Q1-YTD-2025`, `Q2-YTD-2025`, etc.
- `YTD-2024`, `YTD-2025`, etc.

#### Header Parsing Logic
Splits column headers into `Dates` + `Header`:
```
Q3-QTD-2025       → Dates: Q3-QTD-2025,  Header: (empty)
Q3-2025 IS        → Dates: Q3-2025,      Header: IS
Q3-2025 WM        → Dates: Q3-2025,      Header: WM
YTD-2024 Trading  → Dates: YTD-2024,     Header: Trading
```

#### Excluded Columns
Unit indicator headers are automatically excluded:
- `$ in millions`, `$ in billions`
- `in millions`, `in billions`
- `$ (in thousands)`, `in thousands`

### 2. Integration with Exporter

**Modified**: `./src/infrastructure/extraction/exporters/csv_exporter/exporter.py`

**Changes**:
1. Added `enable_data_normalization` parameter to `__init__`
2. Initialized `DataNormalizer` component
3. Applied normalization as the **final step** in `_process_sheet` (after metadata injection)
4. Updated factory function `get_csv_exporter` to support the new parameter

**Default Behavior**: Data normalization is **disabled by default** (`enable_data_normalization=False`) to maintain backward compatibility.

### 3. Transformation Example

#### Input (Wide Format)
```csv
Source,Section,Table Title,Category,Product/Entity,Q3-QTD-2025,Q3-2025 IS,Q3-2025 WM
10q0925.pdf_pg7,Business,Financial Info,Results,Net revenues,$18,224,$5,000,$3,500
10q0925.pdf_pg7,Business,Financial Info,Results,ROE,18.0%,12.0%,25.0%
```

#### Output (Long Format)
```csv
Source,Section,Table Title,Category,Product/Entity,Dates,Header,Data Value
10q0925.pdf_pg7,Business,Financial Info,Results,Net revenues,Q3-QTD-2025,,$18,224
10q0925.pdf_pg7,Business,Financial Info,Results,Net revenues,Q3-2025,IS,$5,000
10q0925.pdf_pg7,Business,Financial Info,Results,Net revenues,Q3-2025,WM,$3,500
10q0925.pdf_pg7,Business,Financial Info,Results,ROE,Q3-QTD-2025,,18.0%
10q0925.pdf_pg7,Business,Financial Info,Results,ROE,Q3-2025,IS,12.0%
10q0925.pdf_pg7,Business,Financial Info,Results,ROE,Q3-2025,WM,25.0%
```

---

## Testing

### Test Suite: `test_data_normalizer.py`

**Location**: `./tests/test_data_normalizer.py`

**Test Coverage**:
1.  **Simple Period Headers** - Period columns without suffix
2.  **Period with Suffix** - Headers like `Q3-2025 IS`, `Q3-2025 WM`
3.  **Mixed Period Types** - QTD, YTD, and quarterly periods
4.  **Unit Indicator Exclusion** - `$ in millions` columns are filtered out
5.  **Row Count Expansion** - N rows × M periods = N*M output rows
6.  **Non-Period Headers** - Handles `MS/PF`, `Total`, `% change`
7.  **Empty Values Preserved** - Empty cells and special values like `-` are retained

**Test Results**:  All 7 tests passed

---

## Scripts

### 1. Normalize Existing CSV Files

**Script**: `./scripts/normalize_csv_data.py`

Normalizes existing CSV files in-place.

**Usage**:
```bash
# Normalize a specific workbook
python scripts/normalize_csv_data.py --workbook 10q0925

# Normalize all workbooks
python scripts/normalize_csv_data.py --all
```

### 2. Export with Normalization Enabled

**Script**: `./scripts/export_with_normalization.py`

Re-exports Excel files to CSV with normalization enabled from the start.

**Usage**:
```bash
python scripts/export_with_normalization.py
```

**Output**: Creates normalized CSV files in `./data/csv_output_normalized/`

---

## Usage in Code

### Programmatic Usage

```python
from src.infrastructure.extraction.exporters.csv_exporter import get_csv_exporter

# Create exporter with normalization enabled
exporter = get_csv_exporter(
    enable_category_separation=True,
    enable_data_formatting=True,
    enable_metadata_injection=True,
    enable_data_normalization=True  # ← Enable normalization
)

# Export all workbooks
summary = exporter.export_all()
```

### Standalone DataFrame Normalization

```python
from src.infrastructure.extraction.exporters.csv_exporter.data_normalizer import DataNormalizer
import pandas as pd

# Create normalizer
normalizer = DataNormalizer()

# Load data
df = pd.read_csv('input.csv')

# Normalize
normalized_df = normalizer.normalize_table(df)

# Validate
if normalizer.validate_normalized_output(df, normalized_df):
    normalized_df.to_csv('output.csv', index=False)
```

---

## Edge Cases Handled

###  Non-Period Headers
Columns that don't match period patterns (e.g., `MS/PF`, `Total`) are placed in the `Dates` column with an empty `Header`.

###  Empty Cell Values
Empty values and special indicators (e.g., `-`, `N/M`) are preserved in the `Data Value` column.

###  Multiple Period Columns
Each period column generates N rows (one per original data row).

**Example**: 10 rows × 4 period columns = 40 output rows

###  Unit Indicators
Columns with unit indicator headers are excluded from transformation to avoid treating metadata as data.

---

## Design Decisions

### 1. Normalization as Optional Feature
- **Default**: Disabled (`enable_data_normalization=False`)
- **Reason**: Maintains backward compatibility; users can enable when needed

### 2. Final Transformation Step
- Normalization is applied **after** all other transformations (category separation, formatting, metadata injection)
- **Reason**: Ensures all metadata is properly added before unpivoting

### 3. In-Place vs. New Output
- Supports both in-place normalization and separate output directory
- **Scripts**: 
  - `normalize_csv_data.py` → In-place normalization
  - `export_with_normalization.py` → New output directory (`csv_output_normalized`)

### 4. Validation
- Built-in validation ensures transformation correctness
- **Checks**:
  - Row count matches expected expansion
  - Required columns exist
  - No unexpected data loss

---

## Files Created/Modified

### New Files
| File | Purpose |
|------|---------|
| `src/infrastructure/extraction/exporters/csv_exporter/data_normalizer.py` | Core normalization logic |
| `tests/test_data_normalizer.py` | Comprehensive test suite |
| `scripts/normalize_csv_data.py` | CLI tool for in-place normalization |
| `scripts/export_with_normalization.py` | Re-export with normalization enabled |
| `req_update/column_data_populated/date_column_value_separation_implementation.md` | This implementation summary |

### Modified Files
| File | Changes |
|------|---------|
| `src/infrastructure/extraction/exporters/csv_exporter/exporter.py` | Added normalization support and integration |

---

## Verification Steps

### 1. Run Tests
```bash
PYTHONPATH=/Users/nitin/Desktop/Chatbot/Morgan/ python3 tests/test_data_normalizer.py
```

**Expected**: All 7 tests pass 

### 2. Normalize a Sample Workbook
```bash
python scripts/normalize_csv_data.py --workbook 10q0925
```

**Expected**: CSV files transformed from wide to long format

### 3. Re-Export with Normalization
```bash
python scripts/export_with_normalization.py
```

**Expected**: New normalized CSV files in `./data/csv_output_normalized/`

---

## Status

| Step | Status |
|------|--------|
| Plan Created |  |
| Core Module Implemented |  |
| Integration Complete |  |
| Tests Written |  |
| Tests Passed |  |
| Scripts Created |  |
| Documentation Complete |  |

---

## Next Steps

1. **Test on Real Data**: Run normalization on actual CSV files to validate with production data
2. **Performance Optimization**: If needed, optimize for large DataFrames
3. **Update Main Pipeline**: Consider adding normalization as a configurable step in the main data processing pipeline
4. **Index Update**: Update `Index.csv` to reflect the new normalized table structure (optional)

---

## References

- **Plan Document**: `./req_update/column_data_populated/date_column_value_separation_plan.md`
- **Exporter Documentation**: Previous implementation plans for category separation, formatting, and metadata injection
