# Query System Demo & ChromaDB Metadata

**Date:** 2025-11-30  
**Status:** ✅ **WORKING**

---

## 🔍 QUERY DEMONSTRATION

### Query Executed
```bash
.venv/bin/python main.py query "What financial tables are available?"
```

### Direct Vector Search Results
```
✅ Found 4 results:

--- Result 1 ---
Score: 1.4928
Table: Table 1 (Rows 1-10)
Source: 10k1222-1-20.pdf
Page: 1
Content: Trading symbols and exchange information

--- Result 2 ---
Score: 1.5299
Table: Table 1 (Rows 8-11)
Source: 10k1222-1-20.pdf
Page: 1
Content: Trading symbols and exchange information (continued)

--- Result 3 ---
Score: 1.6232
Table: Table 11 (Rows 8-12)
Source: 10k1222-1-20.pdf
Page: 11
Content: Financial metrics and categories

--- Result 4 ---
Score: 1.7576
Table: Table 11 (Rows 1-10)
Source: 10k1222-1-20.pdf
Page: 11
Content: Financial metrics and categories
```

**Note:** Lower scores are better (distance-based similarity)

---

## 📊 CHROMADB METADATA STRUCTURE

### Complete Metadata Schema

ChromaDB stores **23 metadata fields** for each table chunk:

```json
{
  "document_id": "d4ecd73cf0cf0a9f86f29b78d49a980d",
  "source_doc": "10k1222-1-20.pdf",
  "page_no": 1,
  
  "company_name": "Morgan Stanley",
  "company_ticker": "MS",
  
  "filing_type": "10-K",
  "report_type": "10-K",
  "year": 2022,
  
  "table_title": "Table 1 (Rows 1-10)",
  "table_index": 0,
  "column_count": 3,
  "row_count": 10,
  "table_structure": "simple",
  "has_multi_level_headers": false,
  "column_headers": "Title of each class|Trading Symbol(s)|Name of exchange on which registered",
  
  "has_currency": true,
  "currency": "USD",
  "is_consolidated": true,
  
  "extraction_backend": "docling",
  "quality_score": 26.5,
  "chunk_type": "complete",
  
  "embedding_model": "sentence-transformers/all-MiniLM-L6-v2",
  "embedding_dimension": 384,
  "embedding_provider": "langchain_huggingface"
}
```

---

## 📋 METADATA FIELDS BREAKDOWN

### Document Information
| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `document_id` | str | MD5 hash of PDF | `d4ecd73c...` |
| `source_doc` | str | Original filename | `10k1222-1-20.pdf` |
| `page_no` | int | Page number | `1` |

### Company Information
| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `company_name` | str | Company name | `Morgan Stanley` |
| `company_ticker` | str | Stock ticker | `MS` |

### Financial Context
| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `filing_type` | str | SEC filing type | `10-K` |
| `report_type` | str | Report type | `10-K` |
| `year` | int | Fiscal year | `2022` |

### Table Structure
| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `table_title` | str | Table identifier | `Table 1 (Rows 1-10)` |
| `table_index` | int | Table position in doc | `0` |
| `column_count` | int | Number of columns | `3` |
| `row_count` | int | Number of rows | `10` |
| `table_structure` | str | Structure type | `simple`, `multi_column`, `multi_header` |
| `has_multi_level_headers` | bool | Multi-level headers | `false` |
| `column_headers` | str | Column names | `Title\|Symbol\|Exchange` |

### Financial Metadata
| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `has_currency` | bool | Contains currency | `true` |
| `currency` | str | Currency type | `USD` |
| `is_consolidated` | bool | Consolidated statement | `true` |

### Extraction Metadata
| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `extraction_backend` | str | Backend used | `docling` |
| `quality_score` | float | Extraction quality | `26.5` |
| `chunk_type` | str | Chunk type | `complete` |

### Embedding Metadata
| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `embedding_model` | str | Model name | `all-MiniLM-L6-v2` |
| `embedding_dimension` | int | Vector dimension | `384` |
| `embedding_provider` | str | Provider | `langchain_huggingface` |

---

## 🔎 METADATA USAGE

### Filtering Examples

You can filter queries using any metadata field:

```python
# Filter by year
results = vector_store.search(
    query_text="revenue",
    filter={"year": 2022}
)

# Filter by company
results = vector_store.search(
    query_text="assets",
    filter={"company_ticker": "MS"}
)

# Filter by table structure
results = vector_store.search(
    query_text="financial data",
    filter={"table_structure": "multi_column"}
)

# Multiple filters
results = vector_store.search(
    query_text="balance sheet",
    filter={
        "year": 2022,
        "has_currency": True,
        "filing_type": "10-K"
    }
)
```

---

## 🎯 METADATA DESIGN RATIONALE

### Why These Fields?

1. **Document Tracking** - Trace back to source PDF and page
2. **Company Context** - Multi-company support (future)
3. **Temporal Filtering** - Year-based queries
4. **Table Structure** - Handle different table types
5. **Financial Context** - Currency, consolidation info
6. **Quality Metrics** - Track extraction quality
7. **Embedding Info** - Model versioning and compatibility

### ChromaDB Constraints

ChromaDB metadata must be:
- ✅ **Simple types only:** `str`, `int`, `float`, `bool`
- ❌ **No complex types:** No lists, dicts, or objects
- ✅ **Filterable:** All fields can be used in `filter` parameter

---

## 📈 CURRENT DATABASE STATUS

**Collection:** `financial_tables`  
**Total Documents:** 4  
**Embedding Model:** sentence-transformers/all-MiniLM-L6-v2  
**Dimension:** 384  
**Source:** Morgan Stanley 10-K (2020)

---

## 🚀 NEXT STEPS

### To Query the System

```bash
# Interactive mode
.venv/bin/python main.py interactive

# Direct query
.venv/bin/python main.py query "Show me balance sheet data"

# Python API
from src.vector_store.stores.chromadb_store import get_vector_store
vector_store = get_vector_store()
results = vector_store.search(query_text="revenue", top_k=5)
```

### To Add More Data

```bash
# Extract more PDFs
.venv/bin/python main.py extract --source raw_data

# Download and extract
.venv/bin/python main.py pipeline --yr 20-25
```

---

## 💡 TIPS

1. **Use metadata filters** for precise queries
2. **Lower scores are better** (distance-based)
3. **Check `quality_score`** for extraction reliability
4. **Use `table_structure`** to find complex tables
5. **Filter by `year`** for temporal analysis
