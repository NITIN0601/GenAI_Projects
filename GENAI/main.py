#!/usr/bin/env python3
"""
Production-Ready Financial RAG System - Main Entry Point

High-Level Architecture:
1. Document Extraction:
   - Download PDFs from URLs
   - Extract with Docling (10Q, 10K documents)
   - Store in Vector DB with hierarchical metadata
   
2. User Query:
   - User Query → Cache System → Vector DB → Response

Usage:
    # Download and process documents
    python main.py download --yr 20-25 --m 03
    python main.py extract --source ../raw_data
    
    # Query system
    python main.py query "What was revenue in Q1 2025?"
    python main.py interactive
    
    # Utilities
    python main.py stats
    python main.py clear-cache
"""

import typer
from typing import Optional, List
from rich.console import Console
from rich.table import Table as RichTable
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
from pathlib import Path
import time
import hashlib
from datetime import datetime

# Import our modules
from download import download_files, get_file_names_to_download
from extract_structure_correct import extract_document_structure_correct
from embeddings.multi_level_embeddings import MultiLevelEmbeddingGenerator
from embeddings.embedding_manager import get_embedding_manager
from embeddings.vector_store import get_vector_store
from rag.query_processor import get_query_processor
from cache.redis_cache import get_redis_cache

app = typer.Typer(help="Financial RAG System - Production Pipeline")
console = Console()

# Base URL for Morgan Stanley filings
BASE_URL = "https://www.morganstanley.com/content/dam/msdotcom/en/about-us-ir/shareholder"


def get_pdf_hash(pdf_path: str) -> str:
    """Get MD5 hash of PDF file for caching."""
    with open(pdf_path, 'rb') as f:
        return hashlib.md5(f.read()).hexdigest()


def is_pdf_in_vectordb(pdf_hash: str) -> bool:
    """Check if PDF is already processed and in vector DB."""
    try:
        vector_store = get_vector_store()
        results = vector_store.search(
            query_text="test",
            top_k=1,
            filter={"document_id": pdf_hash[:12]}
        )
        return len(results) > 0
    except:
        return False


@app.command()
def download(
    yr: str = typer.Option(..., "--yr", help="Year or range (e.g., 25 or 20-25)"),
    m: Optional[str] = typer.Option(None, "--m", help="Month (03, 06, 09, 12) or None for all"),
    output_dir: str = typer.Option("../raw_data", "--output", "-o", help="Output directory"),
    timeout: int = typer.Option(30, "--timeout", help="Download timeout in seconds"),
    max_retries: int = typer.Option(3, "--retries", help="Max retry attempts")
):
    """
    Download PDF files from Morgan Stanley investor relations.
    
    Examples:
        python main.py download --yr 25 --m 03  # Q1 2025
        python main.py download --yr 20-25      # All quarters 2020-2025
    """
    console.print("\n[bold green]📥 Downloading PDF Files[/bold green]\n")
    
    try:
        # Get file URLs to download
        file_urls = get_file_names_to_download(BASE_URL, m, yr)
        
        console.print(f"[cyan]Files to download:[/cyan] {len(file_urls)}")
        for url in file_urls:
            filename = url.split("/")[-1]
            console.print(f"  • {filename}")
        console.print()
        
        # Download files
        results = download_files(
            file_urls=file_urls,
            download_dir=output_dir,
            timeout=timeout,
            max_retries=max_retries
        )
        
        # Summary
        if results['successful']:
            console.print(f"\n[bold green]✓ Successfully downloaded {len(results['successful'])} files[/bold green]")
        if results['failed']:
            console.print(f"[bold red]✗ Failed to download {len(results['failed'])} files[/bold red]")
            
    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(code=1)


@app.command()
def extract(
    source: str = typer.Option("../raw_data", "--source", "-s", help="Directory with PDF files"),
    force: bool = typer.Option(False, "--force", "-f", help="Force re-extraction (ignore cache)"),
    levels: List[str] = typer.Option(["table", "row"], "--levels", "-l", help="Embedding levels")
):
    """
    Extract tables from PDFs using Docling and store in Vector DB.
    
    This is the core extraction pipeline:
    1. Check if PDF already in Vector DB (skip if exists, unless --force)
    2. Extract with Docling (hierarchical structure)
    3. Generate multi-level embeddings
    4. Store in Vector DB with metadata
    
    Examples:
        python main.py extract --source ../raw_data
        python main.py extract --force  # Re-extract all
    """
    console.print("\n[bold green]📊 Extracting Tables with Docling[/bold green]\n")
    
    # Get PDF files
    source_path = Path(source)
    if not source_path.exists():
        console.print(f"[red]Error: Directory {source} does not exist[/red]")
        raise typer.Exit(code=1)
    
    pdf_files = list(source_path.glob("*.pdf"))
    if not pdf_files:
        console.print(f"[red]No PDF files found in {source}[/red]")
        raise typer.Exit(code=1)
    
    console.print(f"Found {len(pdf_files)} PDF files\n")
    
    # Initialize components
    vector_store = get_vector_store()
    embedding_manager = get_embedding_manager()
    generator = MultiLevelEmbeddingGenerator(embedding_manager.model)
    
    # Process each PDF
    stats = {
        'processed': 0,
        'skipped': 0,
        'failed': 0,
        'total_tables': 0,
        'total_embeddings': 0
    }
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        console=console
    ) as progress:
        
        main_task = progress.add_task("Processing PDFs...", total=len(pdf_files))
        
        for pdf_path in pdf_files:
            filename = pdf_path.name
            pdf_hash = get_pdf_hash(str(pdf_path))
            
            # Check cache
            if not force and is_pdf_in_vectordb(pdf_hash):
                console.print(f"[yellow]⚡ {filename} - Already in Vector DB (skipped)[/yellow]")
                stats['skipped'] += 1
                progress.update(main_task, advance=1)
                continue
            
            try:
                # Extract with Docling
                console.print(f"[cyan]Processing {filename}...[/cyan]")
                structure = extract_document_structure_correct(str(pdf_path))
                
                tables_count = len(structure['tables_with_context'])
                console.print(f"  ✓ Extracted {tables_count} tables")
                
                if tables_count == 0:
                    console.print(f"  [yellow]⚠ No tables found[/yellow]")
                    stats['skipped'] += 1
                    progress.update(main_task, advance=1)
                    continue
                
                # Generate embeddings
                # Convert structure to enhanced document format
                from models.enhanced_schemas import EnhancedDocument, DocumentMetadata
                
                doc_metadata = DocumentMetadata(
                    filename=filename,
                    file_hash=pdf_hash,
                    total_pages=len(structure.get('sections', [])),
                    company_name="Morgan Stanley"
                )
                
                enhanced_doc = EnhancedDocument(
                    metadata=doc_metadata,
                    tables=[]  # Would populate from structure
                )
                
                # Generate embeddings with hierarchical metadata
                embeddings = generator.generate_document_embeddings(
                    enhanced_doc,
                    levels=levels
                )
                
                console.print(f"  ✓ Generated {len(embeddings)} embeddings")
                
                # Store in Vector DB
                if embeddings:
                    ids = [e["id"] for e in embeddings]
                    vectors = [e["vector"] for e in embeddings]
                    metadatas = [e["metadata"] for e in embeddings]
                    documents = [e["text"] for e in embeddings]
                    
                    vector_store.add_chunks(
                        ids=ids,
                        embeddings=vectors,
                        metadatas=metadatas,
                        documents=documents
                    )
                    
                    console.print(f"  [green]✓ Stored in Vector DB[/green]")
                    
                    stats['processed'] += 1
                    stats['total_tables'] += tables_count
                    stats['total_embeddings'] += len(embeddings)
                else:
                    console.print(f"  [yellow]⚠ No embeddings generated[/yellow]")
                    stats['skipped'] += 1
                
            except Exception as e:
                console.print(f"  [red]✗ Error: {e}[/red]")
                stats['failed'] += 1
            
            progress.update(main_task, advance=1)
    
    # Summary
    console.print(f"\n[bold]Extraction Summary:[/bold]")
    console.print(f"  Processed: {stats['processed']}")
    console.print(f"  Skipped (cached): {stats['skipped']}")
    console.print(f"  Failed: {stats['failed']}")
    console.print(f"  Total Tables: {stats['total_tables']}")
    console.print(f"  Total Embeddings: {stats['total_embeddings']}")
    console.print()


@app.command()
def query(
    question: str = typer.Argument(..., help="Question to ask"),
    top_k: int = typer.Option(5, "--top-k", "-k", help="Number of results"),
    no_cache: bool = typer.Option(False, "--no-cache", help="Disable cache")
):
    """
    Query the financial data using natural language.
    
    Examples:
        python main.py query "What was revenue in Q1 2025?"
        python main.py query "Compare revenues Q1 2025 vs Q1 2024"
        python main.py query "Show all Fair Value tables"
    """
    console.print(f"\n[bold cyan]Question:[/bold cyan] {question}\n")
    
    try:
        # Get query processor
        processor = get_query_processor()
        
        # Process query
        with console.status("[bold green]Processing query..."):
            result = processor.process_query(question)
        
        # Display result
        console.print(f"[bold green]Answer:[/bold green]")
        console.print(result)
        console.print()
        
    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(code=1)


@app.command()
def interactive():
    """Start interactive query mode."""
    console.print("\n[bold green]🤖 Interactive Query Mode[/bold green]")
    console.print("[dim]Type 'exit' or 'quit' to exit[/dim]\n")
    
    processor = get_query_processor()
    
    while True:
        try:
            question = typer.prompt("\nYour question")
            
            if question.lower() in ['exit', 'quit', 'q']:
                console.print("\n[yellow]Goodbye![/yellow]\n")
                break
            
            # Process query
            with console.status("[bold green]Processing..."):
                result = processor.process_query(question)
            
            console.print(f"\n[bold green]Answer:[/bold green]")
            console.print(result)
            
        except KeyboardInterrupt:
            console.print("\n\n[yellow]Goodbye![/yellow]\n")
            break
        except Exception as e:
            console.print(f"\n[red]Error: {e}[/red]")


@app.command()
def stats():
    """Show system statistics."""
    console.print("\n[bold]System Statistics[/bold]\n")
    
    # Vector DB stats
    try:
        vector_store = get_vector_store()
        vs_stats = vector_store.get_stats()
        
        table = RichTable(title="Vector Database")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="green")
        
        table.add_row("Total Embeddings", str(vs_stats.get('total_chunks', 0)))
        table.add_row("Unique Documents", str(vs_stats.get('unique_documents', 0)))
        
        console.print(table)
        console.print()
    except Exception as e:
        console.print(f"[red]Vector DB Error: {e}[/red]\n")
    
    # Cache stats
    try:
        cache = get_redis_cache()
        if cache.enabled:
            cache_stats = cache.get_stats()
            
            table = RichTable(title="Cache")
            table.add_column("Metric", style="cyan")
            table.add_column("Value", style="green")
            
            table.add_row("Total Keys", str(cache_stats.get('total_keys', 0)))
            table.add_row("Memory Used", cache_stats.get('memory_used', 'N/A'))
            
            console.print(table)
        else:
            console.print("[yellow]Cache is disabled[/yellow]")
    except Exception as e:
        console.print(f"[yellow]Cache not available: {e}[/yellow]")
    
    console.print()


@app.command()
def clear_cache():
    """Clear Redis cache."""
    try:
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
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")


@app.command()
def pipeline(
    yr: str = typer.Option(..., "--yr", help="Year or range (e.g., 25 or 20-25)"),
    m: Optional[str] = typer.Option(None, "--m", help="Month (03, 06, 09, 12)"),
    source: str = typer.Option("../raw_data", "--source", help="Download directory"),
    force: bool = typer.Option(False, "--force", help="Force re-extraction")
):
    """
    Run complete pipeline: Download → Extract → Ready for queries.
    
    Example:
        python main.py pipeline --yr 20-25
    """
    console.print("\n[bold green]🚀 Running Complete Pipeline[/bold green]\n")
    
    # Step 1: Download
    console.print("[bold]Step 1: Downloading PDFs[/bold]")
    download(yr=yr, m=m, output_dir=source)
    
    # Step 2: Extract
    console.print("\n[bold]Step 2: Extracting Tables[/bold]")
    extract(source=source, force=force)
    
    console.print("\n[bold green]✓ Pipeline Complete![/bold green]")
    console.print("[cyan]System is ready for queries. Try:[/cyan]")
    console.print("  python main.py query \"What was revenue in Q1 2025?\"")
    console.print("  python main.py interactive")
    console.print()


if __name__ == "__main__":
    app()
