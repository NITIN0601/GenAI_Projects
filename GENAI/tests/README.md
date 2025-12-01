# Tests Directory

This directory contains all test files organized by type.

## Structure

```
tests/
├── unit/           # Unit tests for individual components
├── integration/    # Integration tests with external systems
└── system/         # End-to-end system tests
```

## Running Tests

### All Tests
```bash
cd /Users/nitin/Desktop/Chatbot/Morgan/GENAI
python3 -m pytest tests/
```

### Unit Tests Only
```bash
python3 -m pytest tests/unit/
```

### Integration Tests Only
```bash
python3 -m pytest tests/integration/
```

### System Tests Only
```bash
python3 -m pytest tests/system/
```

### Individual Test File
```bash
python3 tests/unit/test_header_flattening.py
```

## Test Categories

### Unit Tests (`tests/unit/`)
- **test_header_flattening.py** - Tests multi-line header flattening logic
- **test_spanning_headers.py** - Tests centered spanning header formatting
- **test_chunking.py** - Tests table chunking with overlap

### Integration Tests (`tests/integration/`)
- **test_docling_sample.py** - Tests Docling PDF extraction
- **test_real_tables.py** - Tests extraction on real PDF tables
- **test_extraction.py** - Tests full extraction pipeline

### System Tests (`tests/system/`)
- **test_system.py** - End-to-end system tests
- **test_query_engine.py** - Tests RAG query engine

## Test Data

Test PDFs are located in:
- `/Users/nitin/Desktop/Chatbot/Morgan/raw_data/`

## Notes

- Integration tests require Docling models (downloaded on first run)
- System tests require ChromaDB running
- Some tests may take several minutes (PDF processing)
