# Execution Guide: Financial RAG System

This guide provides step-by-step instructions to execute the Financial RAG system, from data extraction to querying, using **Local Embeddings** and **Local LLM**.

## Prerequisites

Ensure you have the required dependencies installed:
```bash
pip install -r requirements.txt
```

## Configuration Check

Ensure your `.env` file (or environment variables) is configured for local execution. 
If you don't have a `.env` file, the system defaults to:
- **Embedding Provider**: `local` (sentence-transformers)
- **LLM Provider**: `ollama` (local)
- **Vector DB**: `faiss` (local file system)

> [!NOTE]
> Ensure you have [Ollama](https://ollama.ai/) installed and running with `llama2` pulled (`ollama pull llama2`) if you plan to use the query functionality.

## Execution Steps

### 1. Download Financial Documents
Download 10-K and 10-Q filings for Morgan Stanley (or configured ticker).
```bash
# Download filings for the last 5 years (2020-2025)
python main.py download --yr 20-25
```

### 2. Extract Data & Store in Vector DB
This step extracts tables from the downloaded PDFs, generates embeddings locally, and stores them in the FAISS vector database.
```bash
# Extract from the default raw_data directory
python main.py extract
```
*Note: This process may take some time depending on the number of PDFs and your machine's speed.*

### 3. Verify Data Storage
Check the system statistics to confirm data has been indexed.
```bash
python main.py stats
```
You should see a count of "Total Embeddings" greater than 0.

### 4. Query the System
Now you can ask questions about the financial data.

**Single Query:**
```bash
python main.py query "What was the revenue in Q1 2024?"
```

**Interactive Mode:**
```bash
python main.py interactive
```

### 5. Consolidate Tables (Optional)
To export specific tables across multiple quarters to Excel/CSV:
```bash
python main.py consolidate "Contractual principals and fair value"
```

## Troubleshooting

- **"No PDF files found"**: Ensure you ran the `download` command first or placed PDFs in `raw_data/`.
- **"Ollama connection failed"**: Make sure Ollama is running (`ollama serve`).
- **"Vector DB empty"**: If `stats` shows 0 embeddings after extraction, check the logs in `.logs/` for extraction errors.
