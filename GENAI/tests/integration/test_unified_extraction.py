#!/usr/bin/env python3
"""
Test unified extraction system with multiple backends and fallback.
"""

from rich.console import Console
from rich.table import Table as RichTable
from rich.panel import Panel
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from extraction import UnifiedExtractor, extract_pdf

console = Console()


def test_basic_extraction():
    """Test basic extraction with default settings."""
    console.print("\n[bold cyan]Test 1: Basic Extraction[/bold cyan]")
    console.print("=" * 70)
    
    pdf_path = "/Users/nitin/Desktop/Chatbot/Morgan/raw_data/10k1222-1-20.pdf"
    
    if not Path(pdf_path).exists():
        console.print(f"[red]PDF not found: {pdf_path}[/red]")
        return
    
    # Simple extraction
    console.print(f"\nExtracting: {Path(pdf_path).name}")
    result = extract_pdf(pdf_path)
    
    # Display results
    console.print(f"\n[bold]Results:[/bold]")
    console.print(f"  Backend used: [cyan]{result.backend.value}[/cyan]")
    console.print(f"  Quality score: [green]{result.quality_score:.1f}[/green]")
    console.print(f"  Tables found: {len(result.tables)}")
    console.print(f"  Extraction time: {result.extraction_time:.2f}s")
    
    if result.tables:
        console.print(f"\n[bold]First table preview:[/bold]")
        first_table = result.tables[0]['content'][:300]
        console.print(Panel(first_table, border_style="green"))


def test_with_fallback():
    """Test extraction with fallback mechanism."""
    console.print("\n[bold cyan]Test 2: Extraction with Fallback[/bold cyan]")
    console.print("=" * 70)
    
    pdf_path = "/Users/nitin/Desktop/Chatbot/Morgan/raw_data/10k1222-1-20.pdf"
    
    if not Path(pdf_path).exists():
        console.print(f"[red]PDF not found: {pdf_path}[/red]")
        return
    
    # Create extractor with multiple backends
    extractor = UnifiedExtractor(
        backends=["docling", "pymupdf"],
        min_quality=75.0,  # Higher threshold
        enable_caching=True
    )
    
    console.print(f"\nExtracting with fallback enabled...")
    console.print(f"Min quality threshold: 75.0")
    
    result = extractor.extract(pdf_path)
    
    # Display results
    console.print(f"\n[bold]Results:[/bold]")
    console.print(f"  Backend used: [cyan]{result.backend.value}[/cyan]")
    console.print(f"  Quality score: [green]{result.quality_score:.1f}[/green]")
    console.print(f"  Tables found: {len(result.tables)}")
    console.print(f"  Extraction time: {result.extraction_time:.2f}s")


def test_caching():
    """Test caching mechanism."""
    console.print("\n[bold cyan]Test 3: Caching Mechanism[/bold cyan]")
    console.print("=" * 70)
    
    pdf_path = "/Users/nitin/Desktop/Chatbot/Morgan/raw_data/10k1222-1-20.pdf"
    
    if not Path(pdf_path).exists():
        console.print(f"[red]PDF not found: {pdf_path}[/red]")
        return
    
    extractor = UnifiedExtractor(enable_caching=True)
    
    # First extraction (no cache)
    console.print("\n[yellow]First extraction (no cache):[/yellow]")
    result1 = extractor.extract(pdf_path)
    console.print(f"  Time: {result1.extraction_time:.2f}s")
    
    # Second extraction (from cache)
    console.print("\n[yellow]Second extraction (from cache):[/yellow]")
    result2 = extractor.extract(pdf_path)
    console.print(f"  Time: {result2.extraction_time:.2f}s")
    
    # Cache stats
    stats = extractor.get_stats()
    console.print(f"\n[bold]Cache stats:[/bold]")
    if 'cache' in stats:
        cache_stats = stats['cache']
        console.print(f"  Total files: {cache_stats['total_files']}")
        console.print(f"  Total size: {cache_stats['total_size_mb']:.2f} MB")
        console.print(f"  TTL: {cache_stats['ttl_hours']} hours")


def test_backend_info():
    """Display backend information."""
    console.print("\n[bold cyan]Test 4: Backend Information[/bold cyan]")
    console.print("=" * 70)
    
    extractor = UnifiedExtractor()
    stats = extractor.get_stats()
    
    # Create table
    table = RichTable(title="Available Backends")
    table.add_column("Backend", style="cyan")
    table.add_column("Type", style="magenta")
    table.add_column("Priority", style="yellow")
    table.add_column("Available", style="green")
    table.add_column("Version", style="blue")
    
    for backend in stats['backends']:
        table.add_row(
            backend['name'],
            backend['type'],
            str(backend['priority']),
            "✓" if backend['available'] else "✗",
            backend['version']
        )
    
    console.print(table)


def main():
    """Run all tests."""
    console.print(Panel.fit(
        "[bold]Unified Extraction System - Tests[/bold]",
        border_style="cyan"
    ))
    
    try:
        test_backend_info()
        test_basic_extraction()
        test_with_fallback()
        test_caching()
        
        console.print("\n[bold green]✓ All tests completed![/bold green]\n")
        
    except Exception as e:
        console.print(f"\n[bold red]✗ Error: {e}[/bold red]\n")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
