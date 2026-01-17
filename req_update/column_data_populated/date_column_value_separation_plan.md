# Step 5: Date Column Value Separation Plan

> **Phase**: Data Normalization (Wide → Long Format)  
> **Status**:  Planning  
> **Prerequisite**: Steps 1-4 (Excel to CSV, Category Separation, Metadata Injection, Data Formatting)

---

## 1. Objective

Transform CSV data from **wide format** to **long format** by:
1. Converting period header columns into 3 new columns: `Dates`, `Header`, `Data Value`
2. Each data row becomes multiple rows (one per period column)

---

## 2. Transformation Example

### Input (Wide Format)

```csv
Source,Section,Table Title,Category,Product/Entity,Q3-QTD-2025,Q3-2025 IS,Q3-2025 WM
10q0925.pdf_pg7,Business,Financial Info,Results,Net revenues,$18,224,$5,000,$3,500
10q0925.pdf_pg7,Business,Financial Info,Results,ROE,18.0%,12.0%,25.0%
```

### Output (Long Format)

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

## 3. Column Mapping

### Fixed Columns (unchanged)
- `Source`
- `Section`
- `Table Title`
- `Category`
- `Product/Entity`

### New Columns (from period headers)

| Column | Source | Description |
|--------|--------|-------------|
| `Dates` | Period part of column header | `Q3-QTD-2025`, `Q3-2025`, `YTD-2024` |
| `Header` | Suffix after period (if any) | `IS`, `WM`, `Total`, or empty |
| `Data Value` | Cell value from that column | `$18,224`, `18.0%`, etc. |

---

## 4. Header Parsing Logic

Split column header into `Dates` + `Header`:

```
Column Header         → Dates           + Header

Q3-QTD-2025           → Q3-QTD-2025     + (empty)
Q3-2025               → Q3-2025         + (empty)
Q3-2025 IS            → Q3-2025         + IS
Q3-2025 WM            → Q3-2025         + WM
Q3-QTD-2025 Total     → Q3-QTD-2025     + Total
YTD-2024              → YTD-2024        + (empty)
YTD-2024 Trading      → YTD-2024        + Trading
```

### Simple Rule
1. Match period pattern at start: `Qn-YYYY`, `Qn-QTD-YYYY`, `Qn-YTD-YYYY`, `YTD-YYYY`
2. If there's text after a space → that's the `Header`
3. If no text after period → `Header` is empty

---

## 5. Known Period Patterns

| Pattern | Example | Dates | Header |
|---------|---------|-------|--------|
| `Qn-YYYY` | `Q3-2025` | `Q3-2025` |  |
| `Qn-YYYY suffix` | `Q3-2025 IS` | `Q3-2025` | `IS` |
| `Qn-QTD-YYYY` | `Q3-QTD-2025` | `Q3-QTD-2025` |  |
| `Qn-QTD-YYYY suffix` | `Q3-QTD-2025 Total` | `Q3-QTD-2025` | `Total` |
| `Qn-YTD-YYYY` | `Q3-YTD-2025` | `Q3-YTD-2025` |  |
| `Qn-YTD-YYYY suffix` | `Q3-YTD-2025 IM` | `Q3-YTD-2025` | `IM` |
| `YTD-YYYY` | `YTD-2024` | `YTD-2024` |  |
| `YTD-YYYY suffix` | `YTD-2024 Net Interest` | `YTD-2024` | `Net Interest` |

### Common Suffixes Found (192 unique)
- Segment codes: `IS`, `WM`, `IM`, `I/E`
- Aggregates: `Total`, `Inflows`, `Outflows`
- Value types: `Fair Value`, `Amortized Cost`, `Carrying Value`
- Loan types: `Loans`, `LC`, `HFI`, `HFS`
- Categories: `Trading`, `Net Interest`, `Fees`
- Regions: `Japan`, `France`, `Brazil`, `Germany`
- And more...

---

## 6. Edge Cases

### Case 1: Non-Period Headers
For columns that don't match period pattern (e.g., `MS/PF`, `Total`, `% change`):
- Entire header goes to `Dates`
- `Header` is empty

### Case 2: Empty Cell Values
- Include row with empty `Data Value`
- Preserve special values like `-`, `N/M`

### Case 3: Multiple Period Columns
- Each period column generates N rows (where N = original row count)
- Total rows = original rows × number of period columns

### Case 4: Unit Indicator Headers (EXCLUDED)
Columns with unit indicator headers should be **excluded** from transformation:

| Excluded Headers |
|-----------------|
| `$ in millions` |
| `$ in billions` |
| `in millions` |
| `in billions` |
| `$ (in thousands)` |

**Reason:** These are table format indicators, not period/date columns. They typically appear as the first column header row and should be filtered out before the wide→long transformation.

---

## 7. Implementation

### New Module
**File:** `src/infrastructure/extraction/exporters/csv_exporter/data_normalizer.py`

### Integration
**File:** `src/infrastructure/extraction/exporters/csv_exporter/exporter.py`
- Add `enable_data_normalization` parameter

### Source/Destination
| Input | Output |
|-------|--------|
| `./data/csv_output/[workbook]/[table].csv` | Same file (in-place) |

---

## 8. Verification

### Test 1: Simple Period Headers
```bash
# Input: Q3-QTD-2025, Q3-QTD-2024
# Expected: Dates filled, Header empty
```

### Test 2: Period with Suffix
```bash
# Input: Q3-2025 IS, Q3-2025 WM
# Expected: Dates=Q3-2025, Header=IS or WM
```

### Test 3: Row Count
```bash
# Original: 10 rows × 4 period columns = 40 output rows
```

---

## 9. Status

| Step | Status |
|------|--------|
| Plan Created |  |
| User Approval |  |
| Implementation |  |
| Testing |  |

