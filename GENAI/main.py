"""
Main CLI application for Financial RAG System.

Usage:
    python main.py index --source ../raw_data
    python main.py query "What was the total revenue in Q2 2025?"
    python main.py query "Show balance sheet" --year 2024 --quarter Q3
    python main.py interactive
    python main.py stats
    python main.py clear-cache
"""

import typer
from typing import Optional
from rich.console import Console
from rich.table import Table as RichTable
from rich.progress import Progress, SpinnerColumn, TextColumn
from pathlib import Path
import time

from scrapers import EnhancedPDFScraper, MetadataExtractor
from embeddings import get_embedding_manager, get_vector_store
from rag import get_query_engine
from cache import get_redis_cache
from models.schemas import TableChunk, DocumentProcessingResult
from utils import get_pdf_files, compute_file_hash
from config.settings import settings


app = typer.Typer(help="Financial RAG System - Query financial PDFs with AI")
console = Console()


@app.command()
def index(
    source: str = typer.Option(
        "../raw_data",
        "--source",
        "-s",
        help="Directory containing PDF files"
    ),
    clear_existing: bool = typer.Option(
        False,
        "--clear",
        "-c",
        help="Clear existing index before indexing"
    )
):
    """Index PDF files into the vector database."""
    console.print("\n[bold green]📚 Indexing Financial PDFs[/bold green]\n")
    
    # Get vector store and embedding manager
    vector_store = get_vector_store()
    embedding_manager = get_embedding_manager()
    cache = get_redis_cache()
    
    # Clear existing index if requested
    if clear_existing:
        console.print("[yellow]Clearing existing index...[/yellow]")
        vector_store.clear()
    
    # Get PDF files
    pdf_files = get_pdf_files(source)
    
    if not pdf_files:
        console.print(f"[red]No PDF files found in {source}[/red]")
        return
    
    console.print(f"Found {len(pdf_files)} PDF files\n")
    
    # Process each PDF
    results = []
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console
    ) as progress:
        
        for pdf_path in pdf_files:
            filename = Path(pdf_path).name
            task = progress.add_task(f"Processing {filename}...", total=None)
            
            start_time = time.time()
            
            try:
                # Extract tables
                scraper = EnhancedPDFScraper(pdf_path)
                tables = scraper.extract_all_tables()
                
                if not tables:
                    console.print(f"[yellow]No tables found in {filename}[/yellow]")
                    continue
                
                # Extract metadata and create chunks
                metadata_extractor = MetadataExtractor(filename)
                all_chunks = []
                
                for table in tables:
                    # Get metadata
                    metadata = metadata_extractor.extract_metadata(
                        table_title=table.title,
                        page_no=table.page_number
                    )
                    
                    # Create chunks from table rows
                    for row in table.rows:
                        # Create semantic chunk
                        chunk_text = embedding_manager.create_semantic_chunk(
                            table_title=table.title,
                            headers=table.headers,
                            row=row,
                            metadata_str=f"{metadata.quarter or ''} {metadata.year}, Page {metadata.page_no}"
                        )
                        
                        # Create chunk object
                        chunk = TableChunk(
                            content=chunk_text,
                            metadata=metadata
                        )
                        all_chunks.append(chunk)
                
                # Generate embeddings
                texts = [chunk.content for chunk in all_chunks]
                embeddings = embedding_manager.generate_embeddings_batch(texts, show_progress=False)
                
                # Assign embeddings to chunks
                for chunk, embedding in zip(all_chunks, embeddings):
                    chunk.embedding = embedding
                
                # Add to vector store
                vector_store.add_chunks(all_chunks, show_progress=False)
                
                processing_time = time.time() - start_time
                
                result = DocumentProcessingResult(
                    filename=filename,
                    total_tables=len(tables),
                    total_chunks=len(all_chunks),
                    processing_time=processing_time,
                    success=True
                )
                results.append(result)
                
                progress.update(task, completed=True)
                console.print(f"[green]✓[/green] {filename}: {len(tables)} tables, {len(all_chunks)} chunks ({processing_time:.2f}s)")
                
            except Exception as e:
                console.print(f"[red]✗[/red] {filename}: {str(e)}")
                result = DocumentProcessingResult(
                    filename=filename,
                    total_tables=0,
                    total_chunks=0,
                    processing_time=time.time() - start_time,
                    success=False,
                    error_message=str(e)
                )
                results.append(result)
    
    # Summary
    console.print("\n[bold]Indexing Summary[/bold]")
    total_tables = sum(r.total_tables for r in results if r.success)
    total_chunks = sum(r.total_chunks for r in results if r.success)
    successful = sum(1 for r in results if r.success)
    
    console.print(f"✓ Successfully processed: {successful}/{len(results)} files")
    console.print(f"✓ Total tables indexed: {total_tables}")
    console.print(f"✓ Total chunks created: {total_chunks}")
    console.print()


@app.command()
def query(
    question: str = typer.Argument(..., help="Question to ask"),
    year: Optional[int] = typer.Option(None, "--year", "-y", help="Filter by year"),
    quarter: Optional[str] = typer.Option(None, "--quarter", "-q", help="Filter by quarter (Q1, Q2, Q3, Q4)"),
    top_k: int = typer.Option(5, "--top-k", "-k", help="Number of results to retrieve"),
    no_cache: bool = typer.Option(False, "--no-cache", help="Disable cache")
):
    """Ask a question about the financial data."""
    console.print(f"\n[bold cyan]Question:[/bold cyan] {question}\n")
    
    # Build filters
    filters = {}
    if year:
        filters['year'] = year
    if quarter:
        filters['quarter'] = quarter.upper()
    
    # Get query engine
    query_engine = get_query_engine()
    
    # Execute query
    response = query_engine.query(
        query=question,
        filters=filters if filters else None,
        top_k=top_k,
        use_cache=not no_cache
    )
    
    # Display response
    query_engine.display_response(response)
    console.print()


@app.command()
def interactive():
    """Start interactive query mode."""
    query_engine = get_query_engine()
    query_engine.interactive_query()


@app.command()
def stats():
    """Show system statistics."""
    console.print("\n[bold]System Statistics[/bold]\n")
    
    # Vector store stats
    vector_store = get_vector_store()
    vs_stats = vector_store.get_stats()
    
    table = RichTable(title="Vector Store")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")
    
    table.add_row("Total Chunks", str(vs_stats['total_chunks']))
    table.add_row("Unique Documents", str(vs_stats['unique_documents']))
    table.add_row("Years", ", ".join(map(str, vs_stats['years'])))
    
    console.print(table)
    console.print()
    
    # Cache stats
    cache = get_redis_cache()
    cache_stats = cache.get_stats()
    
    if cache_stats.get('enabled'):
        table = RichTable(title="Cache")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="green")
        
        table.add_row("Total Keys", str(cache_stats.get('total_keys', 0)))
        table.add_row("Embedding Keys", str(cache_stats.get('embedding_keys', 0)))
        table.add_row("LLM Keys", str(cache_stats.get('llm_keys', 0)))
        table.add_row("Memory Used", cache_stats.get('memory_used', 'N/A'))
        
        console.print(table)
    else:
        console.print("[yellow]Cache is disabled[/yellow]")
    
    console.print()


@app.command()
def clear_cache():
    """Clear Redis cache."""
    cache = get_redis_cache()
    
    if not cache.enabled:
        console.print("[yellow]Cache is not enabled[/yellow]")
        return
    
    confirm = typer.confirm("Are you sure you want to clear the cache?")
    if confirm:
        cache.clear_all()
        console.print("[green]✓ Cache cleared[/green]")
    else:
        console.print("[yellow]Cancelled[/yellow]")


@app.command()
def rebuild_index():
    """Rebuild the entire index from scratch."""
    confirm = typer.confirm("This will delete all existing data and rebuild the index. Continue?")
    
    if not confirm:
        console.print("[yellow]Cancelled[/yellow]")
        return
    
    # Clear vector store
    vector_store = get_vector_store()
    vector_store.clear()
    
    # Reindex
    index(clear_existing=False)


@app.command()
def setup():
    """Check system setup and dependencies."""
    console.print("\n[bold]System Setup Check[/bold]\n")
    
    checks = []
    
    # Check Ollama
    from rag import get_llm_manager
    llm = get_llm_manager()
    ollama_available = llm.check_availability()
    checks.append(("Ollama", ollama_available))
    
    # Check Redis
    cache = get_redis_cache()
    redis_available = cache.enabled
    checks.append(("Redis", redis_available))
    
    # Check embedding model
    try:
        from embeddings import get_embedding_manager
        emb = get_embedding_manager()
        checks.append(("Embedding Model", True))
    except Exception as e:
        checks.append(("Embedding Model", False))
    
    # Check vector store
    try:
        vector_store = get_vector_store()
        checks.append(("Vector Store", True))
    except Exception as e:
        checks.append(("Vector Store", False))
    
    # Display results
    table = RichTable(title="Component Status")
    table.add_column("Component", style="cyan")
    table.add_column("Status", style="green")
    
    for component, status in checks:
        status_icon = "[green]✓[/green]" if status else "[red]✗[/red]"
        table.add_row(component, status_icon)
    
    console.print(table)
    console.print()
    
    # Recommendations
    if not ollama_available:
        console.print("[yellow]⚠️  Ollama is not running. Install and start it:[/yellow]")
        console.print("   1. Install: https://ollama.ai")
        console.print("   2. Run: ollama serve")
        console.print(f"   3. Pull model: ollama pull {settings.LLM_MODEL}")
        console.print()
    
    if not redis_available:
        console.print("[yellow]⚠️  Redis is not available. To enable caching:[/yellow]")
        console.print("   brew install redis")
        console.print("   brew services start redis")
        console.print()


if __name__ == "__main__":
    app()
