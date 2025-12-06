#!/usr/bin/env python3
"""Test script to verify local embedding and LLM configuration."""

import sys
import os

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config.settings import settings, print_config

print("=" * 80)
print("CONFIGURATION VERIFICATION")
print("=" * 80)

# Print current configuration
print_config()

print("\n" + "=" * 80)
print("TESTING EMBEDDING MANAGER")
print("=" * 80)

try:
    from src.embeddings.manager import get_embedding_manager
    
    embedding_manager = get_embedding_manager()
    print(f"✅ Embedding Manager initialized: {embedding_manager.provider_type}")
    print(f"   Model: {embedding_manager.model_name}")
    
    # Test embedding generation
    test_text = "This is a test"
    embedding = embedding_manager.embed_query(test_text)
    print(f"✅ Test embedding generated: dimension = {len(embedding)}")
    
except Exception as e:
    print(f"❌ Embedding Manager failed: {e}")

print("\n" + "=" * 80)
print("TESTING LLM MANAGER")
print("=" * 80)

try:
    from src.llm.manager import get_llm_manager
    
    print("Initializing LLM Manager (this may take a minute to download the model)...")
    llm_manager = get_llm_manager()
    print(f"✅ LLM Manager initialized: {llm_manager.provider_type}")
    print(f"   Model: {llm_manager.model_name}")
    
    # Test LLM generation
    print("\nTesting LLM generation with a simple prompt...")
    response = llm_manager.generate("What is 2 + 2?")
    print(f"✅ Test generation successful!")
    print(f"   Response: {response[:100]}...")
    
except Exception as e:
    print(f"❌ LLM Manager failed: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 80)
print("VERIFICATION COMPLETE")
print("=" * 80)
