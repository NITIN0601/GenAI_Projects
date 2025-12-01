#!/usr/bin/env python3
"""
Test custom API integration with the provider system.

This script tests that your custom API (with bearer token authentication)
works correctly with the unified provider system.
"""

import sys
sys.path.insert(0, '/Users/nitin/Desktop/Chatbot/Morgan/GENAI')

import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def test_custom_embedding_provider():
    """Test custom embedding API."""
    print("=" * 80)
    print("TESTING CUSTOM EMBEDDING API")
    print("=" * 80)
    
    try:
        from embeddings.custom_api_provider import get_custom_embedding_provider
        
        # Initialize provider
        provider = get_custom_embedding_provider()
        
        # Test single embedding
        print("\n1. Testing single embedding...")
        text = "This is a test sentence for embedding generation."
        embedding = provider.generate_embedding(text)
        
        print(f"   ✓ Generated embedding")
        print(f"   ✓ Dimension: {len(embedding)}")
        print(f"   ✓ Sample values: {embedding[:5]}")
        
        # Test batch embeddings
        print("\n2. Testing batch embeddings...")
        texts = [
            "First test sentence",
            "Second test sentence",
            "Third test sentence"
        ]
        embeddings = provider.generate_embeddings_batch(texts)
        
        print(f"   ✓ Generated {len(embeddings)} embeddings")
        print(f"   ✓ All same dimension: {all(len(e) == len(embeddings[0]) for e in embeddings)}")
        
        print("\n✅ Custom Embedding API working correctly!")
        return True
        
    except Exception as e:
        print(f"\n❌ Custom Embedding API failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_custom_llm_provider():
    """Test custom LLM API."""
    print("\n" + "=" * 80)
    print("TESTING CUSTOM LLM API")
    print("=" * 80)
    
    try:
        from embeddings.custom_api_provider import get_custom_llm_provider
        
        # Initialize provider
        provider = get_custom_llm_provider()
        
        # Test generation
        print("\n1. Testing text generation...")
        prompt = "What is 2+2?"
        response = provider.generate(prompt)
        
        print(f"   ✓ Generated response")
        print(f"   ✓ Response length: {len(response)} characters")
        print(f"   ✓ Response preview: {response[:100]}...")
        
        # Test with context (RAG)
        print("\n2. Testing RAG-style generation...")
        context = "The company's total revenue was $100 million in 2024."
        query = "What was the total revenue?"
        response = provider.generate_with_context(query, context)
        
        print(f"   ✓ Generated contextual response")
        print(f"   ✓ Response: {response[:200]}...")
        
        print("\n✅ Custom LLM API working correctly!")
        return True
        
    except Exception as e:
        print(f"\n❌ Custom LLM API failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_provider_integration():
    """Test integration with existing provider system."""
    print("\n" + "=" * 80)
    print("TESTING PROVIDER SYSTEM INTEGRATION")
    print("=" * 80)
    
    try:
        from embeddings.providers import get_embedding_manager
        
        # Test with custom provider
        print("\n1. Testing EmbeddingManager with custom provider...")
        em = get_embedding_manager(provider="custom")
        
        # Generate embedding
        text = "Test integration with provider system"
        embedding = em.generate_embedding(text)
        
        print(f"   ✓ EmbeddingManager initialized")
        print(f"   ✓ Provider info: {em.get_provider_info()}")
        print(f"   ✓ Embedding dimension: {em.get_dimension()}")
        
        print("\n✅ Provider system integration working!")
        return True
        
    except Exception as e:
        print(f"\n❌ Provider integration failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def check_env_variables():
    """Check if required environment variables are set."""
    print("=" * 80)
    print("CHECKING ENVIRONMENT VARIABLES")
    print("=" * 80)
    
    required_vars = {
        'EB_URL': 'Embedding API URL',
        'EB_MODEL': 'Embedding model name',
        'LLM_URL': 'LLM API URL',
        'LLM_MODEL': 'LLM model name',
        'UNIQUE_ID': 'Unique ID for requests',
        'BEARER_TOKEN': 'Bearer authentication token'
    }
    
    all_set = True
    for var, description in required_vars.items():
        value = os.getenv(var)
        if value:
            # Mask sensitive values
            if 'TOKEN' in var or 'KEY' in var:
                display_value = value[:10] + "..." if len(value) > 10 else "***"
            else:
                display_value = value
            print(f"✓ {var}: {display_value}")
        else:
            print(f"❌ {var}: NOT SET ({description})")
            all_set = False
    
    if not all_set:
        print("\n⚠️  Some environment variables are missing!")
        print("   Please set them in your .env file")
        return False
    
    print("\n✅ All environment variables are set!")
    return True


def main():
    """Run all tests."""
    print("\n")
    print("╔" + "=" * 78 + "╗")
    print("║" + " " * 20 + "CUSTOM API INTEGRATION TEST" + " " * 31 + "║")
    print("╚" + "=" * 78 + "╝")
    print()
    
    # Check environment variables first
    if not check_env_variables():
        print("\n" + "=" * 80)
        print("SETUP REQUIRED")
        print("=" * 80)
        print("\n1. Copy .env.example to .env")
        print("2. Fill in your custom API credentials:")
        print("   - EB_URL, EB_MODEL")
        print("   - LLM_URL, LLM_MODEL")
        print("   - UNIQUE_ID, BEARER_TOKEN")
        print("3. Run this test again")
        return
    
    # Run tests
    results = {
        'Embedding API': test_custom_embedding_provider(),
        'LLM API': test_custom_llm_provider(),
        'Provider Integration': test_provider_integration()
    }
    
    # Summary
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    
    for test_name, passed in results.items():
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{test_name}: {status}")
    
    all_passed = all(results.values())
    
    if all_passed:
        print("\n" + "=" * 80)
        print("🎉 ALL TESTS PASSED!")
        print("=" * 80)
        print("\nYour custom API is now integrated and ready to use!")
        print("\nTo use it in your code:")
        print("  1. Set EMBEDDING_PROVIDER=custom in .env")
        print("  2. Set LLM_PROVIDER=custom in .env")
        print("  3. Run your extraction/RAG pipelines normally")
    else:
        print("\n" + "=" * 80)
        print("⚠️  SOME TESTS FAILED")
        print("=" * 80)
        print("\nPlease check the error messages above and:")
        print("  1. Verify your API credentials are correct")
        print("  2. Ensure your API endpoints are accessible")
        print("  3. Check that your API returns the expected format")


if __name__ == '__main__':
    main()
