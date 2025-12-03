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
    python main.py download --yr 20-25 --m 3
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
import logging

# Configure logging
# Configure logging
from src.utils.logger import setup_logging, get_logger
setup_logging(level="INFO")
logger = get_logger("main")

# Import our modules (updated for new structure)
# Import our modules (updated for new structure)
from scripts.download_documents import download_files, get_file_names_to_download
from src.extraction.extractor import UnifiedExtractor as Extractor
from src.embeddings.multi_level import MultiLevelEmbeddingGenerator
from src.embeddings.manager import get_embedding_manager
from config.settings import settings

# Import vector store manager
from src.vector_store.manager import get_vectordb_manager
from src.models.schemas import TableChunk, TableMetadata

# Optional imports for query functionality
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
        vector_store = get_vectordb_manager()
        # Search returns List[SearchResult]
        results = vector_store.search(
            query="test",
            top_k=1,
            filters={"document_id": pdf_hash[:12]}
        )
        return len(results) > 0
    except Exception as e:
        logger.debug(f"Error checking vector DB: {e}")
        return False

# ... (download command remains same) ...

@app.command()
def extract(
    source: str = typer.Option(None, "--source", "-s", help="Directory with PDF files"),
    force: bool = typer.Option(False, "--force", "-f", help="Force re-extraction (ignore cache)"),
    levels: List[str] = typer.Option(["table", "row"], "--levels", "-l", help="Embedding levels")
):
    """
    Extract tables from PDFs using Docling and store in Vector DB.
    """
    console.print("\n[bold green]📊 Extracting Tables with Docling[/bold green]\n")
    
    # Use settings default if not specified
    if source is None:
        source = settings.RAW_DATA_DIR
    
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
    vector_store = get_vectordb_manager()
    embedding_manager = get_embedding_manager()
    
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
                # Extract with unified system
                console.print(f"  [cyan]Extracting {pdf_path.name}...[/cyan]")
                
                extractor = Extractor(enable_caching=True)
                result = extractor.extract(str(pdf_path))
                
                if not result.is_successful():
                    console.print(f"  [red]✗ Extraction failed: {result.error}[/red]")
                    stats['failed'] += 1
                    progress.update(main_task, advance=1)
                    continue
                
                tables_count = len(result.tables)
                console.print(f"  [green]✓ Extracted {tables_count} tables (quality: {result.quality_score:.1f})[/green]")
                
                if tables_count == 0:
                    console.print(f"  [yellow]⚠ No tables found[/yellow]")
                    stats['skipped'] += 1
                    progress.update(main_task, advance=1)
                    continue
                
                # Generate embeddings and chunks
                console.print(f"  [cyan]→ Generating embeddings...[/cyan]")
                
                chunks_to_store = []
                
                for i, table in enumerate(result.tables):
                    try:
                        content = table.get('content', '')
                        if not content:
                            continue
                            
                        # Generate embedding
                        embedding = embedding_manager.generate_embedding(content)
                        
                        # Extract quarter number and month from quarter string
                        quarter_str = result.metadata.get('quarter')
                        quarter_number = None
                        month = None
                        
                        if quarter_str:
                            # Extract quarter number (Q1 -> 1, Q2 -> 2, etc.)
                            if quarter_str.upper().startswith('Q'):
                                quarter_number = int(quarter_str[1])
                                # Map quarter to ending month (Q1=3, Q2=6, Q3=9, Q4=12)
                                month = quarter_number * 3
                        
                        # Create Metadata with embedding info and temporal fields
                        metadata = TableMetadata(
                            source_doc=filename,
                            page_no=table.get('metadata', {}).get('page_no', 1),
                            table_title=table.get('metadata', {}).get('table_title', f'Table {i+1}'),
                            year=result.metadata.get('year'),
                            quarter=quarter_str,
                            quarter_number=quarter_number,
                            month=month,
                            report_type=result.metadata.get('report_type'),
                            embedding_model=embedding_manager.get_model_name(),
                            embedded_date=datetime.now()
                        )
                        
                        # Create Chunk
                        chunk = TableChunk(
                            chunk_id=f"{pdf_hash}_{i}",
                            content=content,
                            embedding=embedding,
                            metadata=metadata
                        )
                        
                        chunks_to_store.append(chunk)
                        
                    except Exception as e:
                        logger.error(f"Error processing table {i}: {e}")
                        continue
                
                console.print(f"  [green]✓ Generated {len(chunks_to_store)} embeddings[/green]")
                
                # Store in Vector DB
                if chunks_to_store:
                    try:
                        vector_store.add_chunks(chunks_to_store)
                        console.print(f"  [green]✓ Stored {len(chunks_to_store)} chunks in vector DB ({settings.VECTORDB_PROVIDER.upper()})[/green]")
                        
                        stats['processed'] += 1
                        stats['total_tables'] += tables_count
                        stats['total_embeddings'] += len(chunks_to_store)
                    except Exception as e:
                        logger.error(f"Error storing in vector DB: {e}")
                        console.print(f"  [red]✗ Error storing in vector DB: {e}[/red]")
                        stats['failed'] += 1
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
        vector_store = get_vectordb_manager()
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


@app.command()
def consolidate(
    query: str = typer.Argument(..., help="Table title to consolidate (e.g., 'Contractual principals and fair value')"),
    output_dir: str = typer.Option(None, "--output", "-o", help="Output directory"),
    threshold: float = typer.Option(None, "--threshold", "-t", help="Similarity threshold (0.0-1.0)")
):
    """
    Consolidate tables across all quarters/years and export to CSV/Excel.
    
    Searches for tables with matching titles across all PDFs, merges them horizontally,
    and exports to both CSV and Excel formats for anomaly detection analysis.
    
    Examples:
        python main.py consolidate "Contractual principals and fair value"
        python main.py consolidate "Balance Sheet" --output custom_dir
        python main.py consolidate "Revenue" --threshold 0.9
    """
    console.print(f"\\n[bold cyan]🔍 Consolidating Tables:[/bold cyan] '{query}'\\n")
    
    try:
        # Import consolidator
        from src.extraction.consolidation import get_quarterly_consolidator
        from src.embeddings.manager import get_embedding_manager
        
        # Get vector store and embedding manager
        vector_store = get_vectordb_manager()
        embedding_manager = get_embedding_manager()
        
        # Override settings if provided
        if output_dir:
            settings.OUTPUT_DIR = output_dir
        if threshold:
            settings.TABLE_SIMILARITY_THRESHOLD = threshold
        
        # Initialize consolidator
        consolidator = get_quarterly_consolidator(vector_store, embedding_manager)
        
        # Step 1: Find matching tables
        with console.status("[bold green]Searching for matching tables..."):
            tables = consolidator.find_tables_by_title(query, top_k=50)
        
        if not tables:
            console.print("[yellow]⚠ No matching tables found[/yellow]")
            console.print("[dim]Try adjusting the query or lowering the similarity threshold[/dim]")
            return
        
        console.print(f"[green]✓ Found {len(tables)} matching tables[/green]")
        
        # Show found tables
        found_table = RichTable(title="Found Tables")
        found_table.add_column("Quarter", style="cyan")
        found_table.add_column("Year", style="magenta")
        found_table.add_column("Title", style="green")
        found_table.add_column("Score", style="yellow")
        
        for table in tables[:10]:  # Show first 10
            found_table.add_row(
                str(table.get('quarter', 'N/A')),
                str(table.get('year', 'N/A')),
                table.get('title', 'Unknown')[:50],
                f"{table.get('fuzzy_score', 0):.2f}"
            )
        
        console.print(found_table)
        
        # Step 2: Consolidate
        with console.status("[bold green]Consolidating tables..."):
            df, metadata = consolidator.consolidate_tables(tables, table_name=query)
        
        if df.empty:
            console.print("[yellow]⚠ Failed to consolidate tables[/yellow]")
            return
        
        console.print(f"[green]✓ Consolidated: {metadata['total_rows']} rows x {metadata['total_columns']} columns[/green]")
        console.print(f"[cyan]Quarters included: {', '.join(metadata['quarters_included'])}[/cyan]")
        
        # Step 3: Export
        with console.status("[bold green]Exporting to CSV and Excel..."):
            export_paths = consolidator.export(df, query, metadata.get('date_range'))
        
        console.print("\\n[bold green]✓ Export Complete![/bold green]")
        if 'csv' in export_paths:
            console.print(f"  📄 CSV: [cyan]{export_paths['csv']}[/cyan]")
        if 'excel' in export_paths:
            console.print(f"  📊 Excel: [cyan]{export_paths['excel']}[/cyan]")
        
        # Step 4: Preview
        console.print("\\n[bold]Preview (first 10 rows):[/bold]")
        preview_df = df.head(10)
        
        # Create rich table for preview
        preview_table = RichTable()
        for col in preview_df.columns:
            preview_table.add_column(str(col)[:20], style="cyan")
        
        for _, row in preview_df.iterrows():
            preview_table.add_row(*[str(val)[:20] for val in row])
        
        console.print(preview_table)
        console.print()
        
        console.print("[dim]Tip: These files are ready for anomaly detection analysis[/dim]")
        
    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        logger.error(f"Consolidation failed: {e}", exc_info=True)
        raise typer.Exit(code=1)


@app.command()
def scheduler(
    action: str = typer.Argument(..., help="start|stop|list|status"),
    daemon: bool = typer.Option(False, "--daemon", help="Run in background (blocking)"),
    days: int = typer.Option(180, "--days", help="Days to look ahead for filings")
):
    """
    Manage automatic filing scheduler.
    
    The scheduler monitors for new SEC filings and automatically downloads them.
    
    Examples:
        python main.py scheduler list              # Show upcoming filings
        python main.py scheduler start             # Start scheduler (foreground)
        python main.py scheduler start --daemon    # Start and keep running
        python main.py scheduler status            # Check status
    """
    try:
        from src.scheduler.scheduler import get_scheduler
        from src.scheduler.filing_calendar import get_filing_calendar
    except ImportError as e:
        console.print(f"[red]Scheduler not available: {e}[/red]")
        console.print("[yellow]Install dependencies: pip install APScheduler>=3.10.0 holidays>=0.45[/yellow]")
        raise typer.Exit(code=1)
    
    if action == "list":
        # Show upcoming filings
        console.print("\n[bold]Upcoming SEC Filings[/bold]\n")
        
        calendar = get_filing_calendar()
        upcoming = calendar.get_upcoming_filings(days_ahead=days)
        
        if not upcoming:
            console.print(f"[yellow]No upcoming filings in next {days} days[/yellow]")
            return
        
        table = RichTable(title=f"Next {len(upcoming)} Filings")
        table.add_column("Report", style="cyan")
        table.add_column("Quarter/Type", style="magenta")
        table.add_column("Predicted Date", style="green")
        table.add_column("Days Until", style="yellow")
        table.add_column("Window", style="dim")
        
        for filing in upcoming:
            table.add_row(
                filing["filing_name"],
                filing["quarter"],
                filing["predicted_date"].strftime("%Y-%m-%d (%A)"),
                str(filing["days_until"]),
                f"{filing['window_start'].strftime('%b %d')}-{filing['window_end'].strftime('%d')}"
            )
        
        console.print(table)
        console.print()
        console.print("[dim]Note: Dates are predictions based on historical patterns[/dim]")
    
    elif action == "start":
        # Start scheduler
        console.print("\n[bold green]🚀 Starting Filing Scheduler[/bold green]\n")
        
        sched = get_scheduler()
        
        # Schedule upcoming filings
        sched.schedule_upcoming_filings(days_ahead=days)
        
        # Add periodic check
        sched.add_manual_check(interval_hours=settings.SCHEDULER_CHECK_INTERVAL_HOURS)
        
        # Start
        sched.start(daemon=daemon)
        
        if not daemon:
            console.print("[green]Scheduler started in background[/green]")
            console.print("[cyan]Run 'python main.py scheduler status' to check status[/cyan]")
        
    elif action == "stop":
        # Stop scheduler
        sched = get_scheduler()
        sched.stop()
        console.print("[yellow]Scheduler stopped[/yellow]")
    
    elif action == "status":
        # Show status
        sched = get_scheduler()
        status = sched.get_status()
        
        console.print("\n[bold]Scheduler Status[/bold]\n")
        console.print(f"Running: {'[green]Yes[/green]' if status['running'] else '[red]No[/red]'}")
        console.print(f"Total Jobs: {status['total_jobs']}")
        
        if status['upcoming_jobs']:
            console.print("\n[bold]Next 10 Jobs:[/bold]")
            for job in status['upcoming_jobs']:
                next_run = job['next_run'].strftime("%Y-%m-%d %H:%M") if job['next_run'] else "Not scheduled"
                console.print(f"  • {job['name']}: {next_run}")
        
        console.print()
    
    else:
        console.print(f"[red]Unknown action: {action}[/red]")
        console.print("[yellow]Valid actions: start, stop, list, status[/yellow]")
        raise typer.Exit(code=1)


if __name__ == "__main__":
    # Auto-start scheduler if enabled in settings
    if settings.SCHEDULER_ENABLED:
        try:
            from src.scheduler.scheduler import get_scheduler
            logger.info("Auto-starting scheduler (SCHEDULER_ENABLED=True)")
            sched = get_scheduler()
            sched.schedule_upcoming_filings(days_ahead=settings.SCHEDULER_LOOKAHEAD_DAYS)
            sched.add_manual_check(interval_hours=settings.SCHEDULER_CHECK_INTERVAL_HOURS)
            sched.start(daemon=False)
        except Exception as e:
            logger.error(f"Failed to auto-start scheduler: {e}")
    
    app()
