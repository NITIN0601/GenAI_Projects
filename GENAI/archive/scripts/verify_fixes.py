
import sys
import os

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.retrieval.search.base import BaseSearchStrategy, SearchConfig
from src.rag.pipeline import QueryEngine
from src.llm.manager import LLMManager

print("Testing BaseSearchStrategy instantiation...")
try:
    # Mock dependencies
    strategy = BaseSearchStrategy(
        vector_store=None,
        embedding_manager=None,
        llm_manager=None,
        config=SearchConfig()
    )
    print("✅ BaseSearchStrategy instantiated successfully")
except Exception as e:
    print(f"❌ BaseSearchStrategy failed: {e}")

print("\nTesting QueryEngine initialization...")
try:
    engine = QueryEngine()
    print("✅ QueryEngine initialized successfully")
except Exception as e:
    print(f"❌ QueryEngine failed: {e}")
