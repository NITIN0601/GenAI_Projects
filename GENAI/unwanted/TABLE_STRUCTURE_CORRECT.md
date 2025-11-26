# Correct Table Structure for Financial Documents

## The Problem with Current Schema

Current schema only has **one set of headers** - but financial tables have **TWO dimensions**:

### Example: "Difference Between Contractual Principal and Fair Value"

```
                          | Contractual Principal | Fair Value | Difference |  ← COLUMN HEADERS
--------------------------|----------------------|------------|------------|
Loans and other receivables ← ROW HEADER
  Nonaccrual loans        |     $13,654         |  $13,037   |   $617    |
  Performing loans        |     $25,432         |  $25,123   |   $309    |
Borrowings               ← ROW HEADER
  Short-term              |      $5,432         |   $5,123   |   $309    |
  Long-term               |     $12,345         |  $12,100   |   $245    |
```

## Correct JSON Structure

```json
{
  "table_id": "page_57_table_1",
  "title": "Difference Between Contractual Principal and Fair Value",
  "page_number": 57,
  "bounding_box": {"x1": 45, "y1": 200, "x2": 550, "y2": 400},
  
  "column_headers": [
    "",  // Empty for row header column
    "Contractual Principal",
    "Fair Value", 
    "Difference"
  ],
  
  "row_headers": [
    "Loans and other receivables",
    "  Nonaccrual loans",
    "  Performing loans",
    "Borrowings",
    "  Short-term",
    "  Long-term"
  ],
  
  "data_cells": [
    ["Loans and other receivables", "", "", ""],  // Header row
    ["  Nonaccrual loans", "$13,654", "$13,037", "$617"],
    ["  Performing loans", "$25,432", "$25,123", "$309"],
    ["Borrowings", "", "", ""],  // Header row
    ["  Short-term", "$5,432", "$5,123", "$309"],
    ["  Long-term", "$12,345", "$12,100", "$245"]
  ],
  
  "structure": {
    "num_rows": 6,
    "num_columns": 4,
    "has_row_headers": true,
    "has_column_headers": true,
    "hierarchical_rows": true,  // Indented rows show hierarchy
    "merged_cells": [
      {"row": 0, "col": 1, "row_span": 1, "col_span": 3}  // If title spans
    ]
  },
  
  "data_types": {
    "column_1": "currency",
    "column_2": "currency",
    "column_3": "currency"
  }
}
```

## What Docling Should Provide

Docling's table extraction should give us:

1. **Column headers** (top row): The metric names
2. **Row headers** (left column): The category names  
3. **Data cells**: The actual values
4. **Hierarchical structure**: Parent-child relationships in rows
5. **Data types**: Currency, numbers, percentages, etc.

## Updated Pydantic Schema

```python
class TableStructure(BaseModel):
    """Complete table structure with both dimensions."""
    
    # Headers
    column_headers: List[str]  # Top row headers
    row_headers: List[str]     # Left column headers
    
    # Data
    data_cells: List[List[str]]  # All cells including headers
    
    # Structure metadata
    num_rows: int
    num_columns: int
    has_row_headers: bool
    has_column_headers: bool
    hierarchical_rows: bool  # If rows have parent-child structure
    
    # Cell metadata
    merged_cells: Optional[List[Dict[str, int]]] = None
    data_types: Optional[Dict[str, str]] = None  # column_1: "currency", etc.


class FinancialTable(BaseModel):
    """Financial table with complete structure."""
    
    title: str
    page_number: int
    table_number_on_page: int
    bounding_box: Optional[Dict[str, float]] = None
    
    # Complete structure
    structure: TableStructure
    
    # Context
    reading_order: Optional[int] = None
    surrounding_text: Optional[str] = None  # Text before/after table
```

## Why This Matters

For the RAG system to answer:
- "What was the contractual principal for nonaccrual loans?" 
  - Need: Row header "Nonaccrual loans" + Column header "Contractual Principal"
  - Answer: $13,654

Without both dimensions, the system can't properly query the table!

## Next Steps

1. Wait for Docling to install
2. Test if Docling provides both row and column headers
3. Update our schema to match
4. Ensure RAG system can query both dimensions
