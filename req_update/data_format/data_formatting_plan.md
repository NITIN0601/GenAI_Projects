# Data Formatting Plan

## Implementation Status:  COMPLETE

**Implementation Date:** 2026-01-15  
**Status:** Implemented and deployed  
**Prerequisite:** Category Separation ( Complete)  
**Summary:** [implementation_summary.md](./implementation_summary.md)

---

## Overview

This document outlines the plan to **retain and apply data formatting** in CSV tables. The goal is to ensure that:
1. **Currency values** have proper `$` symbol and thousand separators
2. **Percentage values** retain the `%` symbol
3. **Negative values** are consistently formatted (parenthetical or minus sign)

> [!IMPORTANT]
> **Key Objective**: This is about **RETAINING** and **APPLYING** formatting to data values. Values like `$1,234` and `17.4%` should be preserved. Values that are missing formatting (like `1234` when it should be `$1,234`) should have formatting applied.

> [!CAUTION]
> **Headers Are NOT Formatted**: Column headers (like `Q3-QTD-2025`, `% change`, `$ in millions`) should **NEVER** have currency/percentage formatting applied. Only the **data values** inside the table body are formatted. Headers are used for **detection only** (to determine if a column contains currency or percentage values).

> [!NOTE]
> **Implementation Approach**: All formatting is done using **pandas** DataFrame operations with `apply()` and custom formatting functions. The data is stored as `object` dtype to preserve string formatting.

---

## Source and Destination Files

> [!NOTE]
> For detailed source and destination information, see [source_destination_plan.md](../source_destination/source_destination_plan.md#3-data-formatting)

**Quick Summary:**
- **Input:** `./data/csv_output/[workbook_name]/[table_name].csv` (after category separation)
- **Output:** Same files transformed in-place with properly formatted data values
- **Key Changes:** Apply currency ($) and percentage (%) formatting while preserving headers

---

## How to Run

### Option 1: Automatic Integration (Recommended)

Data formatting is **automatically applied** during CSV export when enabled:

```python
# In your pipeline code
from src.infrastructure.extraction.exporters.csv_exporter import get_csv_exporter

# Enable data formatting (default: True)
exporter = get_csv_exporter(
    enable_category_separation=True,
    enable_data_formatting=True  # NEW parameter
)

# Export workbook - formatting is applied automatically after category separation
exporter.export_workbook(
    xlsx_path='./data/processed/10q0925_tables.xlsx',
    output_dir='./data/csv_output/10q0925'
)
```

**Where it runs:** Inside `csv_exporter.py` → `_process_sheet()` method

**Processing order:**
1. Load table data from xlsx
2. Apply category separation (add Category column)
3. **Apply data formatting** ← NEW STEP
4. Write formatted CSV to disk

### Option 2: Standalone Formatting (For Existing CSV Files)

To format existing CSV files that have already been exported:

```python
from src.infrastructure.extraction.exporters.csv_exporter.data_formatter import DataFormatter, DataFormatConfig
import pandas as pd

# Load existing CSV
df = pd.read_csv('./data/csv_output/10q0925/2_table_1.csv')

# Create formatter with custom config (optional)
config = DataFormatConfig(
    negative_style='parenthetical',  # or 'minus'
    percentage_decimal_places=1
)
formatter = DataFormatter(config)

# Apply formatting (pass first column header for format detection)
formatted_df = formatter.format_table(df, table_header='$ in millions')

# Save back to same file
formatted_df.to_csv('./data/csv_output/10q0925/2_table_1.csv', index=False)
```

### Option 3: Batch Processing All CSV Files

```python
# Format all CSV files in a directory
import os
from pathlib import Path

csv_dir = Path('./data/csv_output/10q0925')
formatter = DataFormatter()

for csv_file in csv_dir.glob('*.csv'):
    if csv_file.name == 'Index.csv':
        continue  # Skip index file
    
    df = pd.read_csv(csv_file)
    
    # Detect table header from first row or metadata
    # (You may need to read Index.csv to get the original header)
    formatted_df = formatter.format_table(df, table_header='$ in millions')
    
    formatted_df.to_csv(csv_file, index=False)
    print(f'Formatted: {csv_file.name}')
```

### Configuration Options

```python
from dataclasses import dataclass

@dataclass
class DataFormatConfig:
    # Currency settings
    add_currency_symbol: bool = True  # Add $
    add_thousand_separators: bool = True  # Add commas
    negative_style: str = 'parenthetical'  # ($1,234) vs -$1,234
    
    # Percentage settings
    percentage_decimal_places: int = 1  # 18.0% vs 18.00%
    convert_decimal_to_percentage: bool = True  # 0.18 → 18%
    
    # Detection
    use_header_detection: bool = True
    use_row_label_detection: bool = True  # ROE → percentage
    use_column_header_detection: bool = True  # % change → percentage
```

---

## Pandas Implementation Details

### Data Types in Current Pipeline

Based on analysis of the actual data:

| Column Type | Pandas dtype | Example Values |
|-------------|--------------|----------------|
| Mixed (formatted) | `object` | `'$ (2,173)'`, `'$ (579)'`, `-1164` |
| Pure numeric | `int64` | `-1995`, `-5913` |
| Pure float | `float64` | `0.18`, `0.165` |

### Pandas Formatting Approach

```python
import pandas as pd

def format_dataframe(df: pd.DataFrame, table_header: str) -> pd.DataFrame:
    """
    Format a DataFrame using pandas apply().
    
    - Uses vectorized string operations where possible
    - Falls back to apply() for complex formatting
    - Converts columns to object dtype to preserve formatting
    """
    result = df.copy()
    
    # Get data columns (skip Category and Product/Entity)
    data_cols = [c for c in df.columns if c not in ['Category', 'Product/Entity']]
    
    for col in data_cols:
        # Convert to object dtype to allow mixed types
        result[col] = result[col].astype(object)
        
        # Detect column format from header or values
        col_format = detect_column_format(col, df[col])
        
        # Apply formatting function
        result[col] = df[col].apply(
            lambda x: format_value(x, col_format, table_header)
        )
    
    return result
```

---

## Complete Edge Cases (Verified from Real Data)

### All Value Patterns Discovered

Based on comprehensive scan of `./data/processed/*.xlsx` and `./data/csv_output/*.csv`:

#### 1. Currency with Parenthetical Negative (RETAIN)
```
$ (717)     → ($717)
$ (10)      → ($10)
$ (48)      → ($48)
$ (2,840)   → ($2,840)
$ (2,173)   → ($2,173)
$ (579)     → ($579)
$ (2)       → ($2)
```

#### 2. Percentage with Parenthetical Negative (NORMALIZE)
```
(57)%   → -57%
(99)%   → -99%
(5)%    → -5%
(24)%   → -24%
(13)%   → -13%
(7)%    → -7%
(15)%   → -15%
(50)%   → -50%
```

#### 3. Percentage with Space (NORMALIZE)
```
17.4 %   → 17.4%
14.5 %   → 14.5%
1.2 %    → 1.2%
2.80 %   → 2.80%
98.9 %   → 98.9%
99.7 %   → 99.7%
```

#### 4. Percentage Ranges (PRESERVE)
```
1% to 4% (3%)              → 1% to 4% (3%)
12% to 21% (16%)           → 12% to 21% (16%)
54% to 84% (62% / 54%)     → 54% to 84% (62% / 54%)
```

#### 5. Plain Negative Numbers (APPLY CURRENCY FORMAT)
```
-248      → ($248)
-239      → ($239)
-476      → ($476)
-22865    → ($22,865)
-107      → ($107)
-824      → ($824)
```

#### 6. Plain Positive Numbers (APPLY CURRENCY FORMAT)
```
18224     → $18,224
15383     → $15,383
52755     → $52,755
2666      → $2,666
```

#### 7. Decimal Values (Context-Dependent)
```
# In currency context (EPS, per share):
2.8       → $2.80
1.88      → $1.88
7.53      → $7.53

# In percentage/ratio context (ROE, margin):
0.18      → 18.0%
0.131     → 13.1%
0.67      → 67.0%
```

#### 8. Special Values (PRESERVE AS-IS)
```
N/M       → N/M
N/A       → N/A
-         → -
-%        → -%
nan       → (empty)
```

#### 9. Dash Variations (NORMALIZE)
```
$-        → -
$ -       → -
—         → -
```

---

## Format Detection Logic

### Step 1: Table-Level Detection

```python
def detect_table_format(first_col_header: str) -> dict:
    """
    Detect primary format from table header.
    
    Examples:
        "$ in millions" → {'type': 'currency', 'unit': 'millions'}
        "$ in billions" → {'type': 'currency', 'unit': 'billions'}
        "$ in millions, except per share data" → {'type': 'currency', 'has_exceptions': True}
    """
    header_lower = str(first_col_header).lower()
    
    result = {'type': 'number', 'unit': None, 'has_exceptions': False}
    
    if '$' in header_lower or 'dollar' in header_lower:
        result['type'] = 'currency'
        if 'billion' in header_lower:
            result['unit'] = 'billions'
        elif 'million' in header_lower:
            result['unit'] = 'millions'
        if 'except' in header_lower:
            result['has_exceptions'] = True
    
    return result
```

### Step 2: Column-Level Detection

```python
def detect_column_format(col_name: str, col_values: pd.Series) -> str:
    """
    Detect format from column name and values.
    
    Returns: 'currency', 'percentage', 'number'
    """
    col_lower = str(col_name).lower()
    
    # Check column name for % indicator
    if '%' in col_lower or 'change' in col_lower:
        return 'percentage'
    
    # Check if column contains formatted % values
    sample_values = col_values.dropna().head(10).astype(str)
    if any('%' in str(v) for v in sample_values):
        return 'percentage'
    
    return 'default'  # Use table-level format
```

### Step 3: Row-Level Detection (Product/Entity)

```python
def detect_row_format(row_label: str) -> str:
    """
    Detect format from row label.
    
    Examples:
        'ROE' → 'percentage'
        'Expense efficiency ratio' → 'percentage'
        'Pre-tax margin' → 'percentage'
        'Net revenues' → 'currency' (default)
    """
    label_lower = str(row_label).lower()
    
    percentage_keywords = [
        'ratio', 'roe', 'roa', 'rotce', 'margin', 'yield', 
        'rate', 'efficiency', 'as a percentage', 'percent'
    ]
    
    for keyword in percentage_keywords:
        if keyword in label_lower:
            return 'percentage'
    
    return 'currency'  # Default for financial tables
```

---

## Formatting Functions

### Currency Formatter

```python
def format_currency(value: any, negative_style: str = 'parenthetical') -> str:
    """
    Format value as currency with $ and thousand separators.
    
    Args:
        value: The value to format
        negative_style: 'parenthetical' → ($1,234) or 'minus' → -$1,234
    
    Examples:
        18224         → $18,224
        -248          → ($248)
        '$ (717)'     → ($717)
        2.8           → $2.80
        '$-'          → -
        'N/M'         → N/M
    """
    if pd.isna(value):
        return ''
    
    val_str = str(value).strip()
    
    # Preserve special values
    if val_str in ['N/M', 'N/A', 'NM', '-%', '-', '—']:
        return val_str if val_str != '—' else '-'
    
    # Normalize dash values
    if val_str in ['$-', '$ -', '$—', '$ —']:
        return '-'
    
    # Already formatted with $ - normalize spacing
    if '$' in val_str:
        is_negative = '(' in val_str
        clean = val_str.replace('$', '').replace(',', '').replace('(', '').replace(')', '').replace(' ', '')
        try:
            num = float(clean)
            if is_negative:
                num = -abs(num)
            return _format_number_as_currency(num, negative_style)
        except:
            return val_str
    
    # Plain numeric value
    try:
        num = float(str(value).replace(',', ''))
        return _format_number_as_currency(num, negative_style)
    except:
        return str(value)


def _format_number_as_currency(num: float, negative_style: str) -> str:
    """Format a numeric value as currency."""
    # Check if decimal (like EPS: 2.8)
    has_decimal = num != int(num) and abs(num) < 100
    
    if num < 0:
        abs_num = abs(num)
        if has_decimal:
            formatted = f"{abs_num:,.2f}"
        else:
            formatted = f"{abs_num:,.0f}"
        
        if negative_style == 'parenthetical':
            return f"(${formatted})"
        else:
            return f"-${formatted}"
    else:
        if has_decimal:
            return f"${num:,.2f}"
        else:
            return f"${num:,.0f}"
```

### Percentage Formatter

```python
def format_percentage(value: any, decimal_places: int = 1) -> str:
    """
    Format value as percentage with % symbol.
    
    Args:
        value: The value to format
        decimal_places: Decimal places (default 1)
    
    Examples:
        '17.4 %'      → 17.4%
        0.18          → 18.0%
        '(5)%'        → -5.0%
        '-'           → -
        '1% to 4%...' → 1% to 4%... (preserve ranges)
    """
    if pd.isna(value):
        return ''
    
    val_str = str(value).strip()
    
    # Preserve special values
    if val_str in ['N/M', 'N/A', 'NM', '-%', '-', '—']:
        return val_str if val_str != '—' else '-'
    
    # Preserve percentage ranges (contains 'to' or multiple %)
    if ' to ' in val_str.lower() or val_str.count('%') > 1:
        return val_str.replace(' %', '%')  # Just normalize spacing
    
    # Already has % - normalize format
    if '%' in val_str:
        is_negative = '(' in val_str or val_str.startswith('-')
        clean = val_str.replace('%', '').replace('(', '').replace(')', '').replace(' ', '').replace('-', '')
        try:
            num = float(clean)
            if is_negative:
                num = -num
            return f"{num:.{decimal_places}f}%"
        except:
            return val_str.replace(' %', '%')
    
    # Decimal ratio (0.18 → 18.0%)
    try:
        num = float(val_str)
        if -1 <= num <= 1 and num != 0:
            num = num * 100
        return f"{num:.{decimal_places}f}%"
    except:
        return str(value)
```

---

## Complete Implementation

### DataFormatter Class

```python
from dataclasses import dataclass, field
from typing import List, Optional
import pandas as pd


@dataclass
class DataFormatConfig:
    """Configuration for data formatting."""
    
    # Currency settings
    add_currency_symbol: bool = True
    add_thousand_separators: bool = True
    negative_style: str = 'parenthetical'  # 'parenthetical' or 'minus'
    
    # Percentage settings
    percentage_decimal_places: int = 1
    convert_decimal_to_percentage: bool = True  # Convert 0.18 → 18.0%
    
    # Detection settings
    use_header_detection: bool = True
    use_row_label_detection: bool = True
    use_column_header_detection: bool = True
    
    # Special values
    preserve_special_values: List[str] = field(
        default_factory=lambda: ['N/M', 'N/A', 'NM', '-%', '-']
    )


class DataFormatter:
    """
    Formats data values in CSV tables using pandas.
    
    Applies:
    - Currency formatting: $ with thousand separators
    - Percentage formatting: % symbol
    - Negative normalization: parenthetical or minus
    """
    
    def __init__(self, config: DataFormatConfig = None):
        self.config = config or DataFormatConfig()
    
    def format_table(self, df: pd.DataFrame, table_header: str = None) -> pd.DataFrame:
        """
        Format all data columns in the table.
        
        IMPORTANT: Only DATA VALUES are formatted, NOT headers.
        - Column headers (Q3-QTD-2025, % change) remain unchanged
        - Row labels (Product/Entity column) remain unchanged  
        - Only numeric/formatted values in data cells are processed
        
        Args:
            df: DataFrame with Category, Product/Entity, and data columns
            table_header: First column header (e.g., "$ in millions") - used for detection only
        
        Returns:
            DataFrame with formatted data values (headers unchanged)
        """
        result = df.copy()
        
        # Detect table-level format from header (for detection only, not formatting)
        table_format = detect_table_format(table_header) if table_header else {'type': 'currency'}
        
        # Get data columns (skip Category and Product/Entity - these are labels, not data)
        # Headers themselves are NOT formatted, only the values under them
        data_columns = [c for c in df.columns if c not in ['Category', 'Product/Entity']]
        
        for col in data_columns:
            # Convert to object dtype to preserve string formatting
            result[col] = result[col].astype(object)
            
            # Detect column-specific format
            col_format = detect_column_format(col, df[col])
            
            # Apply formatting row by row (to use row label detection)
            for idx, row in df.iterrows():
                value = row[col]
                row_label = row.get('Product/Entity', '')
                
                # Determine format for this cell
                if col_format == 'percentage':
                    cell_format = 'percentage'
                elif self.config.use_row_label_detection:
                    cell_format = detect_row_format(row_label)
                else:
                    cell_format = table_format.get('type', 'currency')
                
                # Apply formatting
                if cell_format == 'percentage':
                    result.at[idx, col] = format_percentage(
                        value, 
                        self.config.percentage_decimal_places
                    )
                elif cell_format == 'currency':
                    result.at[idx, col] = format_currency(
                        value,
                        self.config.negative_style
                    )
                # else: leave as-is
        
        return result
```

---

## Edge Cases Coverage Checklist

### Currency Values 
- [x] Plain positive: `18224` → `$18,224`
- [x] Plain negative: `-248` → `($248)`
- [x] Large negative: `-22865` → `($22,865)`
- [x] Formatted positive: `$ 1,234` → `$1,234`
- [x] Formatted negative: `$ (717)` → `($717)`
- [x] Formatted with comma: `$ (2,173)` → `($2,173)`
- [x] Decimal (EPS): `2.8` → `$2.80`
- [x] Dash: `$-`, `$ -` → `-`

### Percentage Values 
- [x] With space: `17.4 %` → `17.4%`
- [x] Parenthetical negative: `(5)%` → `-5.0%`
- [x] Decimal ratio: `0.18` → `18.0%`
- [x] Large decimal ratio: `0.67` → `67.0%`
- [x] Ranges: `1% to 4% (3%)` → preserved
- [x] Already formatted: `99.7%` → `99.7%`

### Special Values 
- [x] `N/M` → preserved
- [x] `N/A` → preserved
- [x] `-` → preserved
- [x] `-%` → preserved
- [x] `—` (em dash) → `-`
- [x] `nan` → empty string

### Row-Based Detection 
- [x] `ROE` row → percentage format
- [x] `ROTCE` row → percentage format
- [x] `Expense efficiency ratio` → percentage format
- [x] `Pre-tax margin` → percentage format
- [x] `Net revenues` → currency format

### Column-Based Detection 
- [x] `% change` column → percentage format
- [x] `%Change` column → percentage format
- [x] Values with `%` → percentage format

---

## Proposed Changes

### New Files

#### [NEW] `src/infrastructure/extraction/exporters/csv_exporter/data_formatter.py`

Complete implementation of:
- `DataFormatConfig` dataclass
- `DataFormatter` class
- `format_currency()` function
- `format_percentage()` function
- `detect_table_format()` function
- `detect_column_format()` function
- `detect_row_format()` function

### Modified Files

#### [MODIFY] `src/infrastructure/extraction/exporters/csv_exporter/exporter.py`

- Import `DataFormatter`
- Add `enable_data_formatting` parameter (default: `True`)
- Apply formatting after category separation

---

## Verification Plan

### Automated Tests

```bash
python -m pytest tests/unit/test_data_formatter.py -v
```

**Test Cases:**

1. Currency: `18224` → `$18,224`
2. Negative currency: `-248` → `($248)`
3. Formatted currency: `$ (717)` → `($717)`
4. Percentage with space: `17.4 %` → `17.4%`
5. Decimal ratio: `0.18` (ROE) → `18.0%`
6. Negative percentage: `(5)%` → `-5.0%`
7. Percentage range: `1% to 4%` → preserved
8. Special: `N/M` → preserved
9. Dash: `$-` → `-`

### Manual Verification

```bash
python -c "
from src.infrastructure.extraction.exporters.csv_exporter.data_formatter import DataFormatter
import pandas as pd

df = pd.read_csv('./data/csv_output/10q0925/2_table_1.csv')
formatter = DataFormatter()
result = formatter.format_table(df, table_header='$ in millions')
print(result.to_string())
"
```

---

## Success Criteria

1.  All currency values have `$` and thousand separators
2.  All percentage values have `%` symbol
3.  Decimal ratios (ROE, etc.) convert to percentage
4.  Negative values use consistent notation
5.  Special values (`N/M`, `-%`) preserved
6.  Percentage ranges preserved
7.  All discovered edge cases handled

---

## Next Steps

1.  Review and approve this plan
2.  Create `data_formatter.py` module
3.  Implement formatting functions
4.  Add unit tests
5.  Integrate with CSV export pipeline
6.  Validate on sample files
