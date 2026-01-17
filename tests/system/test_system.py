"""
Quick test script to verify the system works.

Run this after installation to test basic functionality.
"""

from rich.console import Console

console = Console()


def test_imports():
    """Test that all modules can be imported."""
    console.print("\n[bold]Testing imports...[/bold]")
    
    try:
        from config import settings
        console.print("[green]✓[/green] Config module")
        
        from models import TableMetadata, TableChunk
        console.print("[green]✓[/green] Models module")
        
        from scrapers import EnhancedPDFScraper, MetadataExtractor
        console.print("[green]✓[/green] Scrapers module")
        
        from embeddings import get_embedding_manager, get_vector_store
        console.print("[green]✓[/green] Embeddings module")
        
        from cache import get_redis_cache
        console.print("[green]✓[/green] Cache module")
        
        from rag import get_llm_manager, get_retriever, get_query_engine
        console.print("[green]✓[/green] RAG module")
        
        console.print("\n[bold green]All imports successful![/bold green]")
        return True
        
    except Exception as e:
        console.print(f"\n[bold red]Import failed: {e}[/bold red]")
        return False


def test_embedding_model():
    """Test embedding model."""
    console.print("\n[bold]Testing embedding model...[/bold]")
    
    try:
        from embeddings import get_embedding_manager
        
        emb_manager = get_embedding_manager()
        
        # Test single embedding
        test_text = "This is a test sentence for embedding generation."
        embedding = emb_manager.generate_embedding(test_text)
        
        console.print(f"[green]✓[/green] Generated embedding with dimension: {len(embedding)}")
        
        # Test batch embeddings
        test_texts = ["First sentence", "Second sentence", "Third sentence"]
        embeddings = emb_manager.generate_embeddings_batch(test_texts, show_progress=False)
        
        console.print(f"[green]✓[/green] Generated {len(embeddings)} batch embeddings")
        
        return True
        
    except Exception as e:
        console.print(f"[red]✗[/red] Embedding test failed: {e}")
        return False


def test_vector_store():
    """Test vector store."""
    console.print("\n[bold]Testing vector store...[/bold]")
    
    try:
        from embeddings import get_vector_store
        from models import TableChunk, TableMetadata
        
        vector_store = get_vector_store()
        
        # Get stats
        stats = vector_store.get_stats()
        console.print(f"[green]✓[/green] Vector store initialized")
        console.print(f"    Total chunks: {stats['total_chunks']}")
        console.print(f"    Unique documents: {stats['unique_documents']}")
        
        return True
        
    except Exception as e:
        console.print(f"[red]✗[/red] Vector store test failed: {e}")
        return False


def test_llm():
    """Test LLM connection."""
    console.print("\n[bold]Testing LLM (Ollama)...[/bold]")
    
    try:
        from rag import get_llm_manager
        
        llm = get_llm_manager()
        
        if llm.check_availability():
            console.print("[green]✓[/green] Ollama is running and accessible")
            
            # Test generation (optional - can be slow)
            # response = llm.generate("Say 'Hello, World!' and nothing else.")
            # console.print(f"[green]✓[/green] LLM response: {response[:50]}...")
            
            return True
        else:
            console.print("[yellow]⚠[/yellow] Ollama is not running")
            console.print("    Start it with: ollama serve")
            return False
        
    except Exception as e:
        console.print(f"[red]✗[/red] LLM test failed: {e}")
        return False


def test_cache():
    """Test Redis cache."""
    console.print("\n[bold]Testing Redis cache...[/bold]")
    
    try:
        from cache import get_redis_cache
        
        cache = get_redis_cache()
        
        if cache.enabled:
            stats = cache.get_stats()
            console.print("[green]✓[/green] Redis is connected")
            console.print(f"    Total keys: {stats.get('total_keys', 0)}")
        else:
            console.print("[yellow]⚠[/yellow] Redis is not enabled")
            console.print("    Start it with: brew services start redis")
        
        return True
        
    except Exception as e:
        console.print(f"[red]✗[/red] Cache test failed: {e}")
        return False


def main():
    """Run all tests."""
    console.print("\n[bold cyan]═══════════════════════════════════════[/bold cyan]")
    console.print("[bold cyan]   Financial RAG System - Test Suite   [/bold cyan]")
    console.print("[bold cyan]═══════════════════════════════════════[/bold cyan]")
    
    results = []
    
    results.append(("Imports", test_imports()))
    results.append(("Embedding Model", test_embedding_model()))
    results.append(("Vector Store", test_vector_store()))
    results.append(("LLM (Ollama)", test_llm()))
    results.append(("Redis Cache", test_cache()))
    
    # Summary
    console.print("\n[bold]Test Summary[/bold]")
    console.print("─" * 40)
    
    for test_name, passed in results:
        status = "[green]PASS[/green]" if passed else "[red]FAIL[/red]"
        console.print(f"{test_name:.<30} {status}")
    
    passed_count = sum(1 for _, p in results if p)
    total_count = len(results)
    
    console.print("─" * 40)
    console.print(f"Total: {passed_count}/{total_count} tests passed")
    
    if passed_count == total_count:
        console.print("\n[bold green]🎉 All tests passed! System is ready.[/bold green]")
    else:
        console.print("\n[bold yellow]⚠️  Some tests failed. Check the output above.[/bold yellow]")
    
    console.print()


if __name__ == "__main__":
    main()
