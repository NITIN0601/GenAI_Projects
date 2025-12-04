#!/usr/bin/env python3
"""
Production-Ready Financial RAG System - Main Entry Point

Pipeline Steps:
1. download  - Download PDF files (respects DOWNLOAD_ENABLED in .env)
2. extract   - Extract tables from PDFs with Docling
3. embed     - Generate embeddings and store in FAISS
4. view-db   - View FAISS DB contents and schema
5. search    - Perform search on FAISS (without LLM)
6. query     - Send to LLM with prompt, get response
7. consolidate - Get consolidated table as timeseries CSV/Excel

Usage:
    # Pipeline steps
    python main.py download --yr 20-25 --m 3
    python main.py extract --source ../raw_data
    python main.py embed --source ../raw_data
    python main.py view-db
    python main.py search "revenue Q1 2025"
    python main.py query "What was revenue in Q1 2025?"
    python main.py consolidate "Balance Sheet" --format both
    
    # Full pipeline
    python main.py pipeline --yr 20-25
    
    # Utilities
    python main.py stats
    python main.py interactive
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
import logging

# Configure logging
from src.utils.logger import setup_logging, get_logger
setup_logging(level="INFO")
logger = get_logger("main")

# Import settings
from config.settings import settings

# Import pipeline steps
from src.pipeline.steps import (
    PipelineStep,
    PipelineResult,
    run_download,
    run_extract,
    run_embed,
    run_view_db,
    run_search,
    run_query,
    run_consolidate,
)

# Import our modules
from scripts.download_documents import download_files, get_file_names_to_download
from src.extraction.extractor import UnifiedExtractor as Extractor
from src.embeddings.manager import get_embedding_manager
from src.vector_store.manager import get_vectordb_manager
from src.models.schemas import TableChunk, TableMetadata

# Optional imports
try:
    from src.retrieval.query_processor import get_query_processor
    QUERY_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Query functionality not available: {e}")
    QUERY_AVAILABLE = False
    get_query_processor = None

try:
    from src.cache.backends.redis_cache import get_redis_cache
    CACHE_AVAILABLE = True
except ImportError:
    CACHE_AVAILABLE = False
    get_redis_cache = None

app = typer.Typer(help="Financial RAG System - Modular Pipeline")
console = Console()

# Base URL moved to settings.DOWNLOAD_BASE_URL


def get_pdf_hash(pdf_path: str) -> str:
    """Get MD5 hash of PDF file."""
    with open(pdf_path, 'rb') as f:
        return hashlib.md5(f.read()).hexdigest()


# ============================================================================
# STEP 1: DOWNLOAD
# ============================================================================

@app.command()
def download(
    yr: str = typer.Option(..., "--yr", help="Year or range (e.g., 25 or 20-25)"),
    m: Optional[str] = typer.Option(None, "--m", help="Month (03, 06, 09, 12)"),
    output_dir: str = typer.Option(None, "--output", "-o", help="Output directory"),
    timeout: int = typer.Option(30, "--timeout", help="Download timeout"),
    max_retries: int = typer.Option(3, "--retries", help="Max retries")
):
    """
    Step 1: Download PDF files (respects DOWNLOAD_ENABLED in .env).
    
    Examples:
        python main.py download --yr 25 --m 03  # Q1 2025
        python main.py download --yr 20-25      # All 2020-2025
    """
    console.print("\n[bold green]📥 Step 1: Download Files[/bold green]\n")
    
    # Check if download is enabled
    if hasattr(settings, 'DOWNLOAD_ENABLED') and not settings.DOWNLOAD_ENABLED:
        console.print("[yellow]⚠ Download disabled (DOWNLOAD_ENABLED=False in .env)[/yellow]")
        console.print("[dim]Set DOWNLOAD_ENABLED=True to enable downloads[/dim]")
        return
    
    result = run_download(
        year_range=yr,
        month=m,
        output_dir=output_dir,
        timeout=timeout,
        max_retries=max_retries
    )
    
    if result.success:
        console.print(f"[green]✓ {result.message}[/green]")
    else:
        console.print(f"[red]✗ Error: {result.error}[/red]")
        raise typer.Exit(code=1)


# ============================================================================
# STEP 2: EXTRACT
# ============================================================================

@app.command()
def extract(
    source: str = typer.Option(None, "--source", "-s", help="PDF directory"),
    force: bool = typer.Option(False, "--force", "-f", help="Force re-extraction")
):
    """
    Step 2: Extract tables from PDFs using Docling.
    
    Example:
        python main.py extract --source ../raw_data
    """
    console.print("\n[bold green]📄 Step 2: Extract Tables[/bold green]\n")
    
    result = run_extract(source_dir=source, force=force)
    
    if result.success:
        console.print(f"[green]✓ {result.message}[/green]")
        console.print(f"[dim]Processed: {result.metadata.get('processed', 0)} files[/dim]")
    else:
        console.print(f"[red]✗ Error: {result.error}[/red]")
        raise typer.Exit(code=1)


# ============================================================================
# STEP 3 & 4: EMBED (includes storing in FAISS)
# ============================================================================

@app.command()
def embed(
    source: str = typer.Option(None, "--source", "-s", help="PDF directory"),
    force: bool = typer.Option(False, "--force", "-f", help="Force re-embedding"),
    local: bool = typer.Option(False, "--local", "-l", help="Use local embeddings (offline mode)")
):
    """
    Steps 3-4: Extract, generate embeddings, and store in VectorDB.
    
    Examples:
        python main.py embed --source ./raw_data
        python main.py embed --source ./raw_data --local  # Offline mode
    """
    console.print("\n[bold green]🔢 Steps 3-4: Extract + Embed + Store[/bold green]\n")
    
    # Override embedding provider if --local flag is set
    if local:
        console.print("[yellow]📴 Offline mode: Using local embeddings[/yellow]\n")
        settings.EMBEDDING_PROVIDER = "local"
    
    # Step 2: Extract
    console.print("[cyan]Extracting tables...[/cyan]")
    extract_result = run_extract(source_dir=source, force=force)
    
    if not extract_result.success:
        console.print(f"[red]✗ Extraction failed: {extract_result.error}[/red]")
        raise typer.Exit(code=1)
    
    console.print(f"[green]✓ {extract_result.message}[/green]")
    
    # Step 4: Embed
    console.print("[cyan]Generating embeddings...[/cyan]")
    embed_result = run_embed(extracted_data=extract_result.data)
    
    if embed_result.success:
        console.print(f"[green]✓ {embed_result.message}[/green]")
    else:
        console.print(f"[red]✗ Embedding failed: {embed_result.error}[/red]")
        raise typer.Exit(code=1)


# ============================================================================
# STEP 5: VIEW-DB
# ============================================================================

@app.command("view-db")
def view_db(
    sample: bool = typer.Option(True, "--sample/--no-sample", help="Show samples"),
    count: int = typer.Option(5, "--count", "-n", help="Sample count"),
    local: bool = typer.Option(False, "--local", "-l", help="Use local embeddings (offline mode)")
):
    """
    Step 5: View FAISS DB contents and schema.
    
    Examples:
        python main.py view-db
        python main.py view-db --count 10
        python main.py view-db --local  # Offline mode
    """
    console.print("\n[bold green]🗄️ Step 5: FAISS Database View[/bold green]\n")
    
    # Override embedding provider if --local flag is set
    if local:
        settings.EMBEDDING_PROVIDER = "local"

    
    result = run_view_db(show_sample=sample, sample_count=count)
    
    if not result.success:
        console.print(f"[red]✗ Error: {result.error}[/red]")
        raise typer.Exit(code=1)
    
    db_info = result.data
    
    # Stats table
    stats_table = RichTable(title="Database Statistics")
    stats_table.add_column("Metric", style="cyan")
    stats_table.add_column("Value", style="green")
    
    stats_table.add_row("Total Chunks", str(db_info['total_chunks']))
    stats_table.add_row("Unique Documents", str(db_info['unique_documents']))
    stats_table.add_row("Unique Tables", str(db_info['unique_tables']))
    stats_table.add_row("Years", ', '.join(map(str, db_info['years'])) or 'N/A')
    stats_table.add_row("Quarters", ', '.join(db_info['quarters']) or 'N/A')
    
    console.print(stats_table)
    console.print()
    
    # Table titles
    if db_info['table_titles']:
        console.print("[bold]Table Titles (first 20):[/bold]")
        for title in db_info['table_titles']:
            console.print(f"  • {title}")
        console.print()
    
    # Samples
    if db_info['samples']:
        samples_table = RichTable(title="Sample Entries")
        samples_table.add_column("Title", style="cyan")
        samples_table.add_column("Year", style="magenta")
        samples_table.add_column("Quarter", style="yellow")
        samples_table.add_column("Source", style="green")
        
        for s in db_info['samples']:
            samples_table.add_row(
                str(s['title'])[:40],
                str(s['year']),
                str(s['quarter']),
                str(s['source'])
            )
        
        console.print(samples_table)
    
    console.print()


# ============================================================================
# STEP 6: SEARCH
# ============================================================================

@app.command()
def search(
    query: str = typer.Argument(..., help="Search query"),
    top_k: int = typer.Option(5, "--top-k", "-k", help="Number of results"),
    year: Optional[int] = typer.Option(None, "--year", "-y", help="Filter by year"),
    quarter: Optional[str] = typer.Option(None, "--quarter", "-q", help="Filter by quarter"),
    local: bool = typer.Option(False, "--local", "-l", help="Use local embeddings (offline mode)")
):
    """
    Step 6: Search FAISS directly (without LLM).
    
    Examples:
        python main.py search "revenue"
        python main.py search "balance sheet" --year 2025 --quarter Q1
        python main.py search "revenue" --local  # Offline mode
    """
    console.print(f"\n[bold green]🔍 Step 6: FAISS Search[/bold green]\n")
    console.print(f"[cyan]Query:[/cyan] {query}\n")
    
    # Override embedding provider if --local flag is set
    if local:
        console.print("[yellow]📴 Offline mode: Using local embeddings[/yellow]\n")
        settings.EMBEDDING_PROVIDER = "local"
    
    filters = {}
    if year:
        filters['year'] = year
    if quarter:
        filters['quarter'] = quarter
    
    result = run_search(query=query, top_k=top_k, filters=filters if filters else None)
    
    if not result.success:
        console.print(f"[red]✗ Error: {result.error}[/red]")
        raise typer.Exit(code=1)
    
    console.print(f"[green]Found {len(result.data)} results[/green]\n")
    
    results_table = RichTable(title="Search Results")
    results_table.add_column("#", style="dim")
    results_table.add_column("Title", style="cyan")
    results_table.add_column("Year", style="magenta")
    results_table.add_column("Qtr", style="yellow")
    results_table.add_column("Score", style="green")
    results_table.add_column("Content Preview", style="dim")
    
    for i, r in enumerate(result.data, 1):
        content_preview = r['content'][:50] + '...' if len(r['content']) > 50 else r['content']
        results_table.add_row(
            str(i),
            str(r['metadata']['title'])[:30],
            str(r['metadata']['year']),
            str(r['metadata']['quarter']),
            f"{r['score']:.3f}",
            content_preview.replace('\n', ' ')
        )
    
    console.print(results_table)
    console.print()


# ============================================================================
# STEP 7: QUERY (with LLM)
# ============================================================================

@app.command()
def query(
    question: str = typer.Argument(..., help="Question to ask"),
    top_k: int = typer.Option(5, "--top-k", "-k", help="Context chunks"),
    no_cache: bool = typer.Option(False, "--no-cache", help="Disable cache"),
    local: bool = typer.Option(False, "--local", "-l", help="Use local embeddings (offline mode)")
):
    """
    Step 7: Query with LLM response.
    
    Examples:
        python main.py query "What was revenue in Q1 2025?"
        python main.py query "What was revenue?" --local  # Offline embeddings
    """
    console.print(f"\n[bold green]🤖 Step 7: LLM Query[/bold green]\n")
    console.print(f"[cyan]Question:[/cyan] {question}\n")
    
    # Override embedding provider if --local flag is set
    if local:
        console.print("[yellow]📴 Offline mode: Using local embeddings[/yellow]\n")
        settings.EMBEDDING_PROVIDER = "local"
    
    result = run_query(question=question, top_k=top_k, use_cache=not no_cache)
    
    if result.success:
        console.print(f"[bold green]Answer:[/bold green]")
        console.print(result.data['answer'])
    else:
        console.print(f"[red]✗ Error: {result.error}[/red]")
        raise typer.Exit(code=1)
    
    console.print()


# ============================================================================
# STEPS 8-9: CONSOLIDATE + EXPORT
# ============================================================================

@app.command()
def consolidate(
    table_title: str = typer.Argument(..., help="Table title to consolidate"),
    output_dir: str = typer.Option(None, "--output", "-o", help="Output directory"),
    format: str = typer.Option("both", "--format", "-f", help="csv, excel, or both"),
    transpose: bool = typer.Option(True, "--transpose/--no-transpose", help="Timeseries format")
):
    """
    Steps 8-9: Consolidate tables and export as timeseries.
    
    Examples:
        python main.py consolidate "Balance Sheet"
        python main.py consolidate "Revenue" --format excel
        python main.py consolidate "Fair Value" --output ./exports
    """
    console.print(f"\n[bold green]📊 Steps 8-9: Consolidate + Export[/bold green]\n")
    console.print(f"[cyan]Table:[/cyan] {table_title}\n")
    
    result = run_consolidate(
        table_title=table_title,
        output_format=format,
        output_dir=output_dir,
        transpose=transpose
    )
    
    if not result.success:
        console.print(f"[red]✗ Error: {result.error}[/red]")
        raise typer.Exit(code=1)
    
    console.print(f"[green]✓ {result.message}[/green]")
    console.print(f"[dim]Rows: {result.metadata.get('total_rows', 0)}, Columns: {result.metadata.get('total_columns', 0)}[/dim]")
    console.print(f"[dim]Quarters: {', '.join(result.metadata.get('quarters_included', []))}[/dim]")
    
    export_paths = result.data.get('export_paths', {})
    if export_paths:
        console.print("\n[bold]Exported Files:[/bold]")
        for fmt, path in export_paths.items():
            console.print(f"  {fmt.upper()}: [cyan]{path}[/cyan]")
    
    console.print()


# ============================================================================
# INTERACTIVE MODE
# ============================================================================

@app.command()
def interactive():
    """Start interactive query mode."""
    console.print("\n[bold green]💬 Interactive Query Mode[/bold green]")
    console.print("[dim]Type 'exit' to quit[/dim]\n")
    
    while True:
        try:
            question = typer.prompt("Your question")
            
            if question.lower() in ['exit', 'quit', 'q']:
                console.print("\n[yellow]Goodbye![/yellow]\n")
                break
            
            result = run_query(question=question)
            
            if result.success:
                console.print(f"\n[bold green]Answer:[/bold green]")
                console.print(result.data['answer'])
            else:
                console.print(f"\n[red]Error: {result.error}[/red]")
            
            console.print()
            
        except KeyboardInterrupt:
            console.print("\n[yellow]Goodbye![/yellow]\n")
            break


# ============================================================================
# FULL PIPELINE
# ============================================================================

@app.command()
def pipeline(
    yr: str = typer.Option(..., "--yr", help="Year or range"),
    m: Optional[str] = typer.Option(None, "--m", help="Month filter"),
    source: str = typer.Option(None, "--source", help="PDF directory"),
    force: bool = typer.Option(False, "--force", help="Force re-processing")
):
    """
    Run complete pipeline: Download → Extract → Embed.
    
    Example:
        python main.py pipeline --yr 20-25
    """
    console.print("\n[bold green]🚀 Running Complete Pipeline[/bold green]\n")
    
    # Use source or settings default
    if source is None:
        source = settings.RAW_DATA_DIR
    
    # Step 1: Download
    console.print("[bold]Step 1: Download[/bold]")
    download_result = run_download(year_range=yr, month=m, output_dir=source)
    if download_result.success:
        console.print(f"  [green]✓ {download_result.message}[/green]")
    else:
        console.print(f"  [yellow]⚠ {download_result.error}[/yellow]")
    
    # Step 2: Extract
    console.print("\n[bold]Step 2: Extract[/bold]")
    extract_result = run_extract(source_dir=source, force=force)
    if extract_result.success:
        console.print(f"  [green]✓ {extract_result.message}[/green]")
    else:
        console.print(f"  [red]✗ {extract_result.error}[/red]")
        raise typer.Exit(code=1)
    
    # Steps 3-4: Embed
    console.print("\n[bold]Steps 3-4: Embed + Store[/bold]")
    embed_result = run_embed(extracted_data=extract_result.data)
    if embed_result.success:
        console.print(f"  [green]✓ {embed_result.message}[/green]")
    else:
        console.print(f"  [red]✗ {embed_result.error}[/red]")
        raise typer.Exit(code=1)
    
    console.print("\n[bold green]✓ Pipeline Complete![/bold green]")
    console.print("[cyan]Ready for queries. Try:[/cyan]")
    console.print("  python main.py view-db")
    console.print("  python main.py search \"revenue\"")
    console.print("  python main.py query \"What was revenue in Q1 2025?\"")
    console.print()


# ============================================================================
# UTILITIES
# ============================================================================

@app.command()
def stats():
    """Show system statistics."""
    console.print("\n[bold]System Statistics[/bold]\n")
    
    # Vector DB stats
    result = run_view_db(show_sample=False)
    if result.success:
        db_info = result.data
        table = RichTable(title="Vector Database")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="green")
        table.add_row("Total Chunks", str(db_info['total_chunks']))
        table.add_row("Unique Documents", str(db_info['unique_documents']))
        console.print(table)
    else:
        console.print(f"[red]Vector DB Error: {result.error}[/red]")
    
    console.print()


@app.command("clear-cache")
def clear_cache():
    """Clear Redis cache."""
    if not CACHE_AVAILABLE:
        console.print("[yellow]Cache not available[/yellow]")
        return
    
    try:
        cache = get_redis_cache()
        if not cache.enabled:
            console.print("[yellow]Cache is not enabled[/yellow]")
            return
        
        if typer.confirm("Clear all cache?"):
            cache.clear_all()
            console.print("[green]✓ Cache cleared[/green]")
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")


if __name__ == "__main__":
    # Auto-start scheduler if enabled
    if hasattr(settings, 'SCHEDULER_ENABLED') and settings.SCHEDULER_ENABLED:
        try:
            from src.scheduler.scheduler import get_scheduler
            logger.info("Auto-starting scheduler")
            sched = get_scheduler()
            sched.schedule_upcoming_filings(days_ahead=getattr(settings, 'SCHEDULER_LOOKAHEAD_DAYS', 180))
            sched.add_manual_check(interval_hours=getattr(settings, 'SCHEDULER_CHECK_INTERVAL_HOURS', 6))
            sched.start(daemon=False)
        except Exception as e:
            logger.error(f"Failed to auto-start scheduler: {e}")
    
    app()
