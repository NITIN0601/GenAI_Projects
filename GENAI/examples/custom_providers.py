#!/usr/bin/env python3
"""
Example: Using the new multi-provider embedding and VectorDB system.

This demonstrates how to:
1. Switch between OpenAI and local embeddings
2. Switch between different VectorDB backends
3. Use the system with minimal code changes
"""

import sys
sys.path.insert(0, '/Users/nitin/Desktop/Chatbot/Morgan/GENAI')

from embeddings.providers import get_embedding_manager
from embeddings.vectordb_manager import get_vectordb_manager
from src.models.schemas import TableChunk, TableMetadata
import uuid


def example_local_setup():
    """Example 1: Using local models (FREE)."""
    print("=" * 80)
    print("EXAMPLE 1: LOCAL SETUP (FREE)")
    print("=" * 80)
    
    # Initialize with local models
    em = get_embedding_manager(provider="local")
    vs = get_vectordb_manager(provider="chromadb")
    
    print(f"\nEmbedding Provider: {em.get_provider_info()}")
    print(f"VectorDB Provider: {vs.get_provider_info()}")
    
    # Generate embeddings
    text = "Total assets were $1.2 trillion in Q2 2025"
    embedding = em.generate_embedding(text)
    
    print(f"\nGenerated embedding dimension: {len(embedding)}")
    print(f"First 5 values: {embedding[:5]}")


def example_openai_setup():
    """Example 2: Using OpenAI (PAID - requires API key)."""
    print("\n" + "=" * 80)
    print("EXAMPLE 2: OPENAI SETUP (PAID)")
    print("=" * 80)
    
    # NOTE: Requires OPENAI_API_KEY environment variable
    try:
        em = get_embedding_manager(
            provider="openai",
            model="text-embedding-3-small"
            # api_key="sk-your-key-here"  # Or set OPENAI_API_KEY env var
        )
        
        print(f"\nEmbedding Provider: {em.get_provider_info()}")
        
        # Generate embeddings
        text = "Total assets were $1.2 trillion in Q2 2025"
        embedding = em.generate_embedding(text)
        
        print(f"Generated embedding dimension: {len(embedding)}")
        print(f"First 5 values: {embedding[:5]}")
        
    except Exception as e:
        print(f"\n⚠️  OpenAI setup failed: {e}")
        print("Set OPENAI_API_KEY environment variable to use OpenAI")


def example_vectordb_switching():
    """Example 3: Switching VectorDB backends."""
    print("\n" + "=" * 80)
    print("EXAMPLE 3: VECTORDB SWITCHING")
    print("=" * 80)
    
    # Create sample chunk
    metadata = TableMetadata(
        source_doc="example.pdf",
        page_no=1,
        table_title="Test Table",
        year=2025,
        quarter="Q2",
        report_type="10-Q"
    )
    
    chunk = TableChunk(
        chunk_id=str(uuid.uuid4()),
        content="| Assets | Amount |\n| Cash | $100 |",
        metadata=metadata
    )
    
    # Try ChromaDB
    print("\n1. Using ChromaDB:")
    vs_chroma = get_vectordb_manager(provider="chromadb")
    print(f"   Provider: {vs_chroma.get_provider_info()['provider']}")
    
    # Try FAISS
    print("\n2. Using FAISS:")
    vs_faiss = get_vectordb_manager(provider="faiss")
    print(f"   Provider: {vs_faiss.get_provider_info()['provider']}")


def example_batch_embeddings():
    """Example 4: Batch embedding generation."""
    print("\n" + "=" * 80)
    print("EXAMPLE 4: BATCH EMBEDDINGS")
    print("=" * 80)
    
    em = get_embedding_manager(provider="local")
    
    texts = [
        "Total assets: $1.2T",
        "Total liabilities: $800B",
        "Shareholders equity: $400B",
        "Revenue: $50B",
        "Net income: $10B"
    ]
    
    print(f"\nGenerating embeddings for {len(texts)} texts...")
    embeddings = em.generate_embeddings_batch(texts, show_progress=True)
    
    print(f"✓ Generated {len(embeddings)} embeddings")
    print(f"  Dimension: {len(embeddings[0])}")


def example_configuration():
    """Example 5: Configuration-based setup."""
    print("\n" + "=" * 80)
    print("EXAMPLE 5: CONFIGURATION-BASED SETUP")
    print("=" * 80)
    
    from config.settings import settings, print_config
    
    print("\nCurrent configuration:")
    print_config()
    
    # Use settings-based initialization
    em = get_embedding_manager()  # Uses settings.EMBEDDING_PROVIDER
    vs = get_vectordb_manager()   # Uses settings.VECTORDB_PROVIDER
    
    print(f"\nInitialized from config:")
    print(f"  Embedding: {em.get_provider_info()['provider']}")
    print(f"  VectorDB: {vs.get_provider_info()['provider']}")


def main():
    """Run all examples."""
    print("\n")
    print("╔" + "=" * 78 + "╗")
    print("║" + " " * 20 + "MULTI-PROVIDER SYSTEM EXAMPLES" + " " * 28 + "║")
    print("╚" + "=" * 78 + "╝")
    
    # Run examples
    example_local_setup()
    example_openai_setup()
    example_vectordb_switching()
    example_batch_embeddings()
    example_configuration()
    
    print("\n" + "=" * 80)
    print("ALL EXAMPLES COMPLETE")
    print("=" * 80)
    print("\nKey Takeaways:")
    print("1. Easy switching between providers via config or code")
    print("2. Same interface for all providers (OpenAI, local, etc.)")
    print("3. Backward compatible with existing code")
    print("4. Production-ready with enterprise features")
    print("\n" + "=" * 80)


if __name__ == '__main__':
    main()
