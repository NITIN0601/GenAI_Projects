# Table Structure Formatter - Usage Examples

## Overview

The `/extraction` module now includes a **Table Structure Formatter** that provides structured output for extracted tables, showing:
- Table title
- Column headers
- Row headers  
- Table dimensions (rows × columns)
- Hierarchical structure detection

## Location

**Module**: `/extraction/table_formatter.py`

## Usage

### Example 1: Format All Tables (Summary)

```python
from extraction import UnifiedExtractor, format_extraction_tables

# Extract tables
extractor = UnifiedExtractor()
result = extractor.extract("document.pdf")

# Format all tables (summary view)
summary = format_extraction_tables(result)
print(summary)
```

**Output**:
```
================================================================================
TABLE STRUCTURE REPORT
================================================================================

File: /path/to/document.pdf
Backend: docling
Total Tables: 4

[TABLE 1]
================================================================================
Table Title: Table 1 (Rows 1-10)
================================================================================

Column Headers: Title of each class | Trading Symbol(s) | Name of exchange on which registered
Row Headers: 

Table Size:
  Columns: 3
  Rows: 10
  Hierarchical Structure: Yes
```

### Example 2: Format Single Table (Detailed)

```python
from extraction import UnifiedExtractor, format_table_structure

# Extract tables
extractor = UnifiedExtractor()
result = extractor.extract("document.pdf")

# Format a specific table with full content
detailed = format_table_structure(result.tables[2])
print(detailed)
```

**Output**:
```
================================================================================
Table Title: Human Capital Metrics
================================================================================

Column Headers: Category | Category | Metric | At December 31, 2022
Row Headers: Employees, Culture, Diversity and Inclusion, Retention

Table Size:
  Columns: 4
  Rows: 10
  Hierarchical Structure: Yes

Table:
--------------------------------------------------------------------------------
| Category                | Metric                              | At December 31, 2022 |
|-------------------------|-------------------------------------|----------------------|
| Employees               | Employees by geography (thousands)  | Americas | 55        |
|                         |                                     | Asia Pacific | 17    |
|                         |                                     | EMEA | 10            |
| Culture                 | Employee engagement                 | 90%                  |
...
--------------------------------------------------------------------------------
```

### Example 3: Programmatic Access

```python
from extraction import UnifiedExtractor, TableStructureFormatter

# Extract
extractor = UnifiedExtractor()
result = extractor.extract("document.pdf")

# Parse table structure
formatter = TableStructureFormatter()
parsed = formatter.parse_markdown_table(result.tables[0]['content'])

# Access structure
print(f"Columns: {parsed['column_count']}")
print(f"Rows: {parsed['row_count']}")
print(f"Column names: {parsed['columns']}")

# Detect hierarchy
hierarchical_rows = formatter.detect_row_hierarchy(parsed['rows'])
for row in hierarchical_rows:
    print(f"Level {row['level']}: {row['category']}")
```

## API Reference

### Functions

#### `format_extraction_tables(extraction_result, include_content=False)`
Format all tables from an extraction result.

**Parameters**:
- `extraction_result`: ExtractionResult object
- `include_content`: Whether to include full table content (default: False)

**Returns**: Formatted string with all table structures

#### `format_table_structure(table_dict, include_content=True)`
Format a single table with structure information.

**Parameters**:
- `table_dict`: Table dictionary from extraction
- `include_content`: Whether to include full table content (default: True)

**Returns**: Formatted string with table structure

### Class: TableStructureFormatter

#### Methods

##### `parse_markdown_table(markdown_content)`
Parse markdown table into structured format.

**Returns**:
```python
{
    'columns': ['Column1', 'Column2', ...],
    'column_count': int,
    'rows': [[cell1, cell2, ...], ...],
    'row_count': int
}
```

##### `detect_row_hierarchy(rows)`
Detect hierarchical structure in row headers.

**Returns**: List of row information with hierarchy level (0, 1, 2)

## Test Script

Run the test script to see the formatter in action:

```bash
python3 test_formatter.py
```

## Integration

The formatter is now part of the `/extraction` module and can be imported directly:

```python
from extraction import (
    UnifiedExtractor,
    format_extraction_tables,
    format_table_structure,
    TableStructureFormatter
)
```

All extraction results can now be formatted with structured output showing table metadata, dimensions, and hierarchy!
