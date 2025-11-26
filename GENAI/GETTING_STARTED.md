# 🚀 Getting Started with Your Financial RAG System

## ✅ What's Been Built

Your complete RAG system is ready! Here's what you have:

- **21 Python files** implementing the full pipeline
- **Enhanced PDF scraping** with 2-column layout support
- **Rich metadata extraction** (Year, Quarter, Table Type, etc.)
- **Vector database** (ChromaDB) for semantic search
- **Free local LLM** (Ollama) - no API keys needed!
- **Redis caching** for performance
- **Beautiful CLI** with multiple commands

## 🎯 Next Steps to Use the System

### Step 1: Install Ollama (Free LLM)

```bash
# Install Ollama
brew install ollama

# Start Ollama (in a separate terminal)
ollama serve

# Pull the model (in another terminal)
ollama pull llama3.2
```

**Note**: Keep `ollama serve` running in a terminal while using the system.

### Step 2: Install Redis (Optional but Recommended)

```bash
# Install Redis
brew install redis

# Start Redis
brew services start redis
```

### Step 3: Install Python Dependencies

```bash
cd /Users/nitin/Desktop/Chatbot/Morgan/GENAI

# Install all dependencies
pip install -r requirements.txt
```

This will install:
- LangChain (RAG framework)
- ChromaDB (vector database)
- sentence-transformers (embeddings)
- pdfplumber (PDF parsing)
- Redis client
- And more...

### Step 4: Test the System

```bash
# Run the test suite
python test_system.py
```

This will verify:
- ✓ All modules can be imported
- ✓ Embedding model loads correctly
- ✓ Vector store initializes
- ✓ Ollama is running
- ✓ Redis is connected

### Step 5: Index Your PDFs

```bash
# Index all PDFs from raw_data directory
python main.py index --source ../raw_data
```

**Expected output:**
```
📚 Indexing Financial PDFs

Found 6 PDF files

✓ 10k1224.pdf: 45 tables, 892 chunks (12.34s)
✓ 10q0320.pdf: 38 tables, 756 chunks (10.21s)
✓ 10q0324.pdf: 32 tables, 634 chunks (9.87s)
✓ 10q0325.pdf: 31 tables, 612 chunks (9.45s)
✓ 10q0625.pdf: 33 tables, 654 chunks (10.12s)
✓ 10q0925.pdf: 35 tables, 693 chunks (10.34s)

Indexing Summary
✓ Successfully processed: 6/6 files
✓ Total tables indexed: 214
✓ Total chunks created: 4,241
```

### Step 6: Start Querying!

```bash
# Ask a simple question
python main.py query "What was the total revenue in Q2 2025?"

# Query with filters
python main.py query "Show balance sheet items" --year 2024 --quarter Q3

# Interactive mode (recommended for exploration)
python main.py interactive
```

## 📚 Quick Reference

### Common Commands

```bash
# Index PDFs
python main.py index --source ../raw_data

# Ask a question
python main.py query "Your question here"

# Interactive mode
python main.py interactive

# View statistics
python main.py stats

# Check system setup
python main.py setup

# Clear cache
python main.py clear-cache

# Rebuild index
python main.py rebuild-index

# Get help
python main.py --help
```

### Example Queries

```bash
# Revenue analysis
python main.py query "What was the total revenue in 2025?"

# Balance sheet
python main.py query "Show total assets" --year 2024

# Cash flow
python main.py query "Operating cash flow in Q2" --quarter Q2

# Comparison
python main.py query "Compare revenue across quarters in 2025"

# Specific table
python main.py query "Show derivative instruments fair value"
```

## 🎓 Interactive Mode (Recommended)

The easiest way to explore:

```bash
python main.py interactive
```

Then ask questions naturally:
```
Your question: What was the total revenue in Q2 2025?
Your question: Show me all balance sheet items
Your question: Compare cash flow across quarters
Your question: exit
```

## 🔧 Troubleshooting

### Ollama not running

```bash
# In a separate terminal
ollama serve

# Then pull the model
ollama pull llama3.2
```

### Redis not available

```bash
# Start Redis
brew services start redis

# Or disable Redis in the code (it will still work)
# Edit config/settings.py: REDIS_ENABLED = False
```

### Import errors

```bash
# Reinstall dependencies
pip install -r requirements.txt
```

### No PDFs found

Make sure your PDFs are in the correct location:
```bash
ls ../raw_data/*.pdf
```

## 📖 Documentation

- **README.md** - Comprehensive documentation
- **walkthrough.md** - Implementation details
- **config/settings.py** - Configuration options
- **main.py** - CLI source code

## 🎯 What You Can Do

Once set up, you can:

1. **Ask Questions** about financial data
   - "What was the revenue in Q2 2025?"
   - "Show balance sheet items"
   - "Compare cash flow"

2. **Filter by Metadata**
   - By year: `--year 2024`
   - By quarter: `--quarter Q3`
   - By table type: automatically detected

3. **Get Citations**
   - Every answer includes source tables
   - Page numbers and document names
   - Confidence scores

4. **Monitor Performance**
   - View statistics
   - Check cache hit rates
   - See indexed documents

## 🚀 Quick Start Script

For the fastest setup, use the automated script:

```bash
cd /Users/nitin/Desktop/Chatbot/Morgan/GENAI
./quickstart.sh
```

This will:
1. Check prerequisites
2. Install dependencies
3. Run tests
4. Index PDFs
5. Show you how to query

## 💡 Tips

- **First run is slow** - Downloading embedding model (~90MB)
- **Keep Ollama running** - It needs to be active for queries
- **Use interactive mode** - Best for exploration
- **Cache helps** - Repeated queries are much faster
- **Filters are smart** - Just mention "Q2 2025" in your query

## 🎉 You're Ready!

Your Financial RAG system is complete and ready to use. Start with:

```bash
cd /Users/nitin/Desktop/Chatbot/Morgan/GENAI
python main.py setup
python main.py index --source ../raw_data
python main.py interactive
```

Enjoy exploring your financial data with AI! 🚀
