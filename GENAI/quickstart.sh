#!/bin/bash

# Quick Start Script for Financial RAG System
# This script helps you get started quickly

set -e  # Exit on error

echo "================================================"
echo "  Financial RAG System - Quick Start Setup"
echo "================================================"
echo ""

# Check if we're in the GENAI directory
if [ ! -f "main.py" ]; then
    echo "❌ Error: Please run this script from the GENAI directory"
    echo "   cd GENAI && ./quickstart.sh"
    exit 1
fi

echo "Step 1: Checking prerequisites..."
echo ""

# Check Python
if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version)
    echo "✓ Python found: $PYTHON_VERSION"
else
    echo "❌ Python 3 not found. Please install Python 3.8+"
    exit 1
fi

# Check Ollama
if command -v ollama &> /dev/null; then
    echo "✓ Ollama found"
    
    # Check if Ollama is running
    if curl -s http://localhost:11434/api/tags &> /dev/null; then
        echo "✓ Ollama is running"
    else
        echo "⚠️  Ollama is installed but not running"
        echo "   Starting Ollama in background..."
        ollama serve &
        sleep 3
    fi
    
    # Check if model is installed
    if ollama list | grep -q "llama3.2"; then
        echo "✓ llama3.2 model found"
    else
        echo "⚠️  llama3.2 model not found"
        echo "   Pulling model (this may take a few minutes)..."
        ollama pull llama3.2
    fi
else
    echo "❌ Ollama not found"
    echo "   Install from: https://ollama.ai"
    echo "   Then run: ollama pull llama3.2"
    exit 1
fi

# Check Redis (optional)
if command -v redis-cli &> /dev/null; then
    if redis-cli ping &> /dev/null; then
        echo "✓ Redis is running"
    else
        echo "⚠️  Redis is installed but not running"
        echo "   Starting Redis..."
        brew services start redis 2>/dev/null || redis-server --daemonize yes
        sleep 2
    fi
else
    echo "⚠️  Redis not found (optional, but recommended)"
    echo "   Install with: brew install redis"
fi

echo ""
echo "Step 2: Installing Python dependencies..."
echo ""

pip3 install -q -r requirements.txt

echo "✓ Dependencies installed"
echo ""

echo "Step 3: Running system tests..."
echo ""

python3 test_system.py

echo ""
echo "Step 4: Indexing sample PDFs..."
echo ""

if [ -d "../raw_data" ]; then
    python3 main.py index --source ../raw_data
else
    echo "⚠️  ../raw_data directory not found"
    echo "   Please ensure your PDFs are in the raw_data directory"
fi

echo ""
echo "================================================"
echo "  Setup Complete! 🎉"
echo "================================================"
echo ""
echo "Try these commands:"
echo ""
echo "  # Ask a question"
echo "  python3 main.py query \"What was the total revenue in Q2 2025?\""
echo ""
echo "  # Interactive mode"
echo "  python3 main.py interactive"
echo ""
echo "  # View statistics"
echo "  python3 main.py stats"
echo ""
echo "  # Get help"
echo "  python3 main.py --help"
echo ""
