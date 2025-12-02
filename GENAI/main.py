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
from src.utils.logging_config import configure_logging, get_logger
configure_logging(log_dir=".logs")
logger = get_logger("main")

# Import our modules (updated for new structure)
from scripts.download_documents import download_files, get_file_names_to_download
from src.extraction.extractor import UnifiedExtractor as Extractor
from src.embeddings.multi_level import MultiLevelEmbeddingGenerator
from src.embeddings.manager import get_embedding_manager
from config.settings import settings

# Import vector store based on configuration
if settings.VECTORDB_PROVIDER == "faiss":
    from src.vector_store.stores.faiss_store import get_faiss_store as get_vector_store
else:
    from src.vector_store.stores.chromadb_store import get_vector_store

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
# Moved to settings in a real scenario, but keeping here for now as requested to fix logging only
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
    except Exception as e:
        logger.debug(f"Error checking vector DB: {e}")
        return False


@app.command()
def download(
    yr: str = typer.Option(..., "--yr", help="Year or range (e.g., 25 or 20-25)"),
    m: Optional[str] = typer.Option(None, "--m", help="Month (03, 06, 09, 12) or None for all"),
    output_dir: str = typer.Option(None, "--output", "-o", help="Output directory"),
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
    
    # Use settings default if not specified
    if output_dir is None:
        output_dir = settings.RAW_DATA_DIR
    
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
    source: str = typer.Option(None, "--source", "-s", help="Directory with PDF files"),
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
        python main.py extract --source raw_data
        python main.py extract --force  # Re-extract all
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
    vector_store = get_vector_store()
    embedding_manager = get_embedding_manager()
    # Note: MultiLevelEmbeddingGenerator will be used later if needed
    
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
                    stats['failed'] += 1 # Assuming 'failed' refers to stats['failed']
                    progress.update(main_task, advance=1)
                    continue
                
                tables_count = len(result.tables)
                console.print(f"  [green]✓ Extracted {tables_count} tables (quality: {result.quality_score:.1f})[/green]")
                
                if tables_count == 0:
                    console.print(f"  [yellow]⚠ No tables found[/yellow]")
                    stats['skipped'] += 1
                    progress.update(main_task, advance=1)
                    continue
                
                # Generate embeddings
                # Convert structure to enhanced document format
                from src.models.enhanced_schemas import EnhancedDocument, DocumentMetadata
                # Generate embeddings for each table
                console.print(f"  [cyan]→ Generating embeddings...[/cyan]")
                
                embeddings_generated = []
                for i, table in enumerate(result.tables):
                    try:
                        # Get table content
                        content = table.get('content', '')
                        if not content:
                            continue
                        
                        # Generate embedding
                        embedding = embedding_manager.generate_embedding(content)
                        
                        # Get table metadata from extraction
                        table_meta = table.get('metadata', {})
                        
                        # Analyze table structure
                        lines = content.split('\n')
                        rows = [line for line in lines if line.strip() and '|' in line]
                        
                        # Extract column headers (first row after separator)
                        column_headers = None
                        row_headers = []  # NEW: Extract row headers
                        row_count = 0
                        column_count = 0
                        separator_idx = None
                        
                        if rows:
                            # Find header row (before separator)
                            for idx, row in enumerate(rows):
                                if '---' in row or '===' in row:
                                    separator_idx = idx
                                    if idx > 0:
                                        header_row = rows[idx-1]
                                        cols = [c.strip() for c in header_row.split('|') if c.strip()]
                                        column_headers = '|'.join(cols)
                                        column_count = len(cols)
                                    # Count data rows (after separator)
                                    row_count = len([r for r in rows[idx+1:] if r.strip() and '---' not in r])
                                    break
                            
                            # NEW: Extract row headers (first column of each data row)
                            if separator_idx is not None and separator_idx < len(rows) - 1:
                                for row in rows[separator_idx+1:]:
                                    if '|' in row and '---' not in row and row.strip():
                                        cells = [c.strip() for c in row.split('|') if c.strip()]
                                        if cells:
                                            row_headers.append(cells[0])  # First column is row header
                        
                        # NEW: Get actual table title and detect chunking
                        import re
                        raw_title = table_meta.get('table_title', f'Table {i+1}')
                        actual_table_title = re.sub(r'\s*\(Rows \d+-\d+\)\s*$', '', raw_title)
                        
                        # NEW: Detect if this is a chunked table
                        is_chunked = 'Rows' in raw_title
                        chunk_overlap = 0
                        if is_chunked:
                            # Extract chunk info from title like "Table 1 (Rows 1-10)"
                            match = re.search(r'Rows (\d+)-(\d+)', raw_title)
                            if match:
                                chunk_start = int(match.group(1))
                                # If not first chunk, assume 3 row overlap (configurable)
                                chunk_overlap = 3 if chunk_start > 1 else 0
                        
                        # NEW: Store table content (limit to 10000 chars for ChromaDB)
                        table_content_summary = content[:10000] if len(content) > 10000 else content
                        
                        # ---------------------------------------------------------
                        # METADATA ENRICHMENT (Refactored)
                        # ---------------------------------------------------------
                        from src.extraction.enrichment import get_metadata_enricher
                        enricher = get_metadata_enricher()
                        
                        # Base metadata from extraction
                        base_metadata = {
                            'table_title': raw_title,
                            'actual_table_title': actual_table_title,
                            'is_chunked': is_chunked,
                            'chunk_overlap': chunk_overlap,
                            'table_content': table_content_summary,
                            'extraction_backend': result.backend.value if hasattr(result.backend, 'value') else 'docling',
                            'quality_score': float(result.quality_score) if result.quality_score else None,
                            'chunk_type': 'complete'
                        }
                        
                        # Enrich with financial context (units, currency, statement type, structure)
                        enriched_metadata = enricher.enrich_table_metadata(
                            content=content,
                            table_title=actual_table_title,
                            existing_metadata=base_metadata
                        )
                        
                        # Get embedding info
                        embedding_info = embedding_manager.get_provider_info()
                        
                        # Build final metadata (filter out None values for ChromaDB)
                        table_metadata = {
                            # Document info
                            'document_id': pdf_hash,
                            'source_doc': filename,
                            'page_no': table_meta.get('page_no', 1),
                            
                            # Company info
                            'company_name': 'Morgan Stanley',  # TODO: Extract from PDF
                            'company_ticker': 'MS',  # TODO: Extract from PDF
                            
                            # Financial context
                            'filing_type': result.metadata.get('report_type', '10-K'),
                            'table_index': i,
                            
                            # Temporal
                            'year': result.metadata.get('year', 2022),
                            
                            # Merged Enriched Metadata
                            **enriched_metadata,
                            
                            # NEW: Row and column headers (still extracted here for now)
                            'row_headers': '|'.join(row_headers[:50]),  # Limit to 50 rows
                            'is_consolidated': True,
                            
                            # Embedding metadata
                            'embedding_model': embedding_info.get('model', 'unknown'),
                            'embedding_dimension': embedding_info.get('dimension', 384),
                            'embedding_provider': embedding_info.get('provider', 'local'),
                        }
                        
                        # Add optional fields only if they have values
                        if result.metadata.get('quarter'):
                            table_metadata['quarter'] = str(result.metadata.get('quarter'))
                        if result.metadata.get('report_type'):
                            table_metadata['report_type'] = str(result.metadata.get('report_type'))
                        if column_headers:
                            table_metadata['column_headers'] = column_headers
                        
                        embeddings_generated.append({
                            'id': f"{pdf_hash}_{i}",
                            'embedding': embedding,
                            'content': content,
                            'metadata': table_metadata
                        })
                    except Exception as e:
                        console.print(f"  [red]Error generating embedding for table {i}: {e}[/red]")
                        logger.error(f"Error generating embedding for table {i}: {e}", exc_info=True)
                        continue
                
                console.print(f"  [green]✓ Generated {len(embeddings_generated)} embeddings[/green]")
                
                # Store in Vector DB
                if embeddings_generated:
                    try:
                        # Add to vector store (supports both FAISS and ChromaDB)
                        if settings.VECTORDB_PROVIDER == "faiss":
                            # FAISS: Store with raw metadata dictionary (preserves all fields)
                            chunks = []
                            for e in embeddings_generated:
                                # Create a simple object with the required attributes
                                class ChunkData:
                                    def __init__(self, chunk_id, content, embedding, metadata):
                                        self.chunk_id = chunk_id
                                        self.content = content
                                        self.embedding = embedding
                                        self.metadata = metadata  # Keep as dict
                                
                                chunk = ChunkData(
                                    chunk_id=e['id'],
                                    content=e['content'],
                                    embedding=e['embedding'],
                                    metadata=e['metadata']  # Pass raw dict
                                )
                                chunks.append(chunk)
                            vector_store.add_chunks(chunks)
                            vector_store.save()  # Persist to disk
                        else:
                            # ChromaDB: Use LangChain API
                            vector_store.vector_db.add_texts(
                                texts=[e['content'] for e in embeddings_generated],
                                embeddings=[e['embedding'] for e in embeddings_generated],
                                metadatas=[e['metadata'] for e in embeddings_generated],
                                ids=[e['id'] for e in embeddings_generated]
                            )
                        console.print(f"  [green]✓ Stored {len(embeddings_generated)} embeddings in vector DB ({settings.VECTORDB_PROVIDER.upper()})[/green]")
                        
                        stats['processed'] += 1
                        stats['total_tables'] += tables_count
                        stats['total_embeddings'] += len(embeddings_generated)
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
        vector_store = get_vector_store()
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
