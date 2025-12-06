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
from typing import Optional
from rich.console import Console
from rich.table import Table as RichTable
import logging

# Configure logging
from src.utils.logger import setup_logging, get_logger
setup_logging(level="INFO")
logger = get_logger("main")

# Import settings
from config.settings import settings

# Import pipeline steps
from src.pipeline.steps import (
    run_download,
    run_extract,
    run_embed,
    run_view_db,
    run_search,
    run_query,
    run_consolidate,
)

# Import CLI helpers
from src.utils.helpers import (
    get_table_id,
    get_table_title,
    set_local_embedding_mode,
    check_download_enabled,
    create_results_table,
    create_db_stats_table,
    export_results_to_csv,
    handle_pipeline_result,
)

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
) -> None:
    """
    Step 1: Download PDF files (respects DOWNLOAD_ENABLED in .env).
    
    Examples:
        python main.py download --yr 25 --m 03  # Q1 2025
        python main.py download --yr 20-25      # All 2020-2025
    """
    console.print("\n[bold green]📥 Step 1: Download Files[/bold green]\n")
    
    if not check_download_enabled():
        return
    
    result = run_download(
        year_range=yr,
        month=m,
        output_dir=output_dir,
        timeout=timeout,
        max_retries=max_retries
    )
    
    handle_pipeline_result(result, show_metadata=False)


# ============================================================================
# STEP 2: EXTRACT
# ============================================================================

@app.command()
def extract(
    source: str = typer.Option(None, "--source", "-s", help="PDF directory"),
    force: bool = typer.Option(False, "--force", "-f", help="Force re-extraction")
) -> None:
    """
    Step 2: Extract tables from PDFs using Docling.
    
    Example:
        python main.py extract --source ../raw_data
    """
    console.print("\n[bold green]📄 Step 2: Extract Tables[/bold green]\n")
    
    result = run_extract(source_dir=source, force=force)
    handle_pipeline_result(result)


# ============================================================================
# STEP 3 & 4: EMBED (includes storing in FAISS)
# ============================================================================

@app.command()
def embed(
    source: str = typer.Option(None, "--source", "-s", help="PDF directory"),
    force: bool = typer.Option(False, "--force", "-f", help="Force re-embedding"),
    local: bool = typer.Option(False, "--local", "-l", help="Use local embeddings (offline mode)")
) -> None:
    """
    Steps 3-4: Extract, generate embeddings, and store in VectorDB.
    
    Examples:
        python main.py embed --source ./raw_data
        python main.py embed --source ./raw_data --local  # Offline mode
    """
    console.print("\n[bold green]🔢 Steps 3-4: Extract + Embed + Store[/bold green]\n")
    
    set_local_embedding_mode(local)
    
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
    
    handle_pipeline_result(embed_result)


# ============================================================================
# STEP 5: VIEW-DB
# ============================================================================

@app.command("view-db")
def view_db(
    sample: bool = typer.Option(True, "--sample/--no-sample", help="Show samples"),
    count: int = typer.Option(5, "--count", "-n", help="Sample count"),
    local: bool = typer.Option(False, "--local", "-l", help="Use local embeddings (offline mode)")
) -> None:
    """
    Step 5: View FAISS DB contents and schema.
    
    Examples:
        python main.py view-db
        python main.py view-db --count 10
        python main.py view-db --local  # Offline mode
    """
    console.print("\n[bold green]🗄️ Step 5: FAISS Database View[/bold green]\n")
    
    set_local_embedding_mode(local)
    
    result = run_view_db(show_sample=sample, sample_count=count)
    
    if not result.success:
        console.print(f"[red]✗ Error: {result.error}[/red]")
        raise typer.Exit(code=1)
    
    db_info = result.data
    
    # Stats table
    console.print(create_db_stats_table(db_info))
    console.print()
    
    # Table titles
    if db_info.get('table_titles'):
        console.print("[bold]Table Titles (first 20):[/bold]")
        for title in db_info['table_titles']:
            console.print(f"  • {title}")
        console.print()
    
    # Samples
    if db_info.get('samples'):
        samples_table = RichTable(title="Sample Entries")
        samples_table.add_column("Table ID", style="dim")
        samples_table.add_column("Title", style="cyan")
        samples_table.add_column("Year", style="magenta")
        samples_table.add_column("Quarter", style="yellow")
        samples_table.add_column("Source", style="green")
        
        for s in db_info['samples']:
            samples_table.add_row(
                str(s.get('table_id', 'N/A')),
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
    local: bool = typer.Option(False, "--local", "-l", help="Use local embeddings (offline mode)"),
    export: bool = typer.Option(False, "--export", "-e", help="Export results to CSV")
) -> None:
    """
    Step 6: Search FAISS directly (without LLM).
    
    Examples:
        python main.py search "revenue"
        python main.py search "balance sheet" --year 2025 --quarter Q1
        python main.py search "revenue" --local  # Offline mode
        python main.py search "revenue" --export  # Export to CSV
    """
    console.print(f"\n[bold green]🔍 Step 6: FAISS Search[/bold green]\n")
    console.print(f"[cyan]Query:[/cyan] {query}\n")
    
    set_local_embedding_mode(local)
    
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
    
    # Display results
    console.print(create_results_table(result.data))
    
    # Export to CSV if requested
    if export:
        csv_path = export_results_to_csv(result.data, query)
        console.print(f"\n[green]✓ Results exported to: {csv_path}[/green]")
    
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
) -> None:
    """
    Step 7: Query with LLM response.
    
    Examples:
        python main.py query "What was revenue in Q1 2025?"
        python main.py query "What was revenue?" --local  # Offline embeddings
    """
    console.print(f"\n[bold green]🤖 Step 7: LLM Query[/bold green]\n")
    console.print(f"[cyan]Question:[/cyan] {question}\n")
    
    set_local_embedding_mode(local)
    
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
) -> None:
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
def interactive() -> None:
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
) -> None:
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
def stats() -> None:
    """Show system statistics."""
    console.print("\n[bold]System Statistics[/bold]\n")
    
    # Vector DB stats
    result = run_view_db(show_sample=False)
    if result.success:
        console.print(create_db_stats_table(result.data))
    else:
        console.print(f"[red]Vector DB Error: {result.error}[/red]")
    
    console.print()


@app.command("clear-cache")
def clear_cache(
    all: bool = typer.Option(False, "--all", "-a", help="Clear everything including vectordb (DESTRUCTIVE)"),
    pycache: bool = typer.Option(False, "--pycache", "-p", help="Clear __pycache__ directories"),
    cache: bool = typer.Option(False, "--cache", "-c", help="Clear application caches"),
    vectordb: bool = typer.Option(False, "--vectordb", "-v", help="Clear vector databases (DESTRUCTIVE)"),
    reports: bool = typer.Option(False, "--reports", "-r", help="Clear extraction reports"),
    dry_run: bool = typer.Option(False, "--dry-run", "-n", help="Preview what would be deleted"),
) -> None:
    """
    Clear cache and temporary files.
    
    Examples:
        python main.py clear-cache                    # Clear pycache + app cache
        python main.py clear-cache --all              # Clear EVERYTHING (destructive!)
        python main.py clear-cache --pycache          # Only __pycache__
        python main.py clear-cache --cache            # Only app caches
        python main.py clear-cache --vectordb         # Only vector databases
        python main.py clear-cache --dry-run          # Preview without deleting
    """
    from src.utils.cleanup import clear_all_cache
    
    # If no specific option, default to pycache + app cache
    if not any([all, pycache, cache, vectordb, reports]):
        include_pycache = True
        include_cache = True
        include_vectordb = False
        include_reports = False
    elif all:
        if not dry_run and not typer.confirm("⚠️  This will delete ALL caches including vectordb. Continue?"):
            console.print("[yellow]Cancelled[/yellow]")
            return
        include_pycache = True
        include_cache = True
        include_vectordb = True
        include_reports = True
    else:
        include_pycache = pycache
        include_cache = cache
        include_vectordb = vectordb
        include_reports = reports
        
        if include_vectordb and not dry_run:
            if not typer.confirm("⚠️  This will delete vector databases. Continue?"):
                console.print("[yellow]Cancelled[/yellow]")
                return
    
    try:
        results = clear_all_cache(
            include_pycache=include_pycache,
            include_app_cache=include_cache,
            include_vectordb=include_vectordb,
            include_reports=include_reports,
            dry_run=dry_run
        )
        
        if not dry_run:
            console.print("[green]✓ Cleanup complete[/green]")
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