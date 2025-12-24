"""Utility functions."""

import hashlib
from pathlib import Path
from typing import Any, List
import os


def compute_file_hash(filepath: str) -> str:
    """
    Compute MD5 hash of a file.
    
    Args:
        filepath: Path to file
        
    Returns:
        MD5 hash string
    """
    hash_md5 = hashlib.md5()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()


def get_pdf_files(directory: str) -> List[str]:
    """
    Get all PDF files in a directory.
    
    Args:
        directory: Directory path
        
    Returns:
        List of PDF file paths
    """
    pdf_files = []
    for file in Path(directory).glob("*.pdf"):
        pdf_files.append(str(file))
    return sorted(pdf_files)


def ensure_directory(directory: str):
    """
    Ensure directory exists, create if not.
    
    Args:
        directory: Directory path
    """
    Path(directory).mkdir(parents=True, exist_ok=True)


def format_number(value: Any) -> str:
    """
    Format number for display.
    
    Args:
        value: Number value
        
    Returns:
        Formatted string
    """
    try:
        num = float(value)
        if num >= 1_000_000_000:
            return f"${num/1_000_000_000:.2f}B"
        elif num >= 1_000_000:
            return f"${num/1_000_000:.2f}M"
        elif num >= 1_000:
            return f"${num/1_000:.2f}K"
        else:
            return f"${num:.2f}"
    except (ValueError, TypeError):
        return str(value)


def truncate_text(text: str, max_length: int = 100) -> str:
    """
    Truncate text to max length.
    
    Args:
        text: Input text
        max_length: Maximum length
        
    Returns:
        Truncated text
    """
    if len(text) <= max_length:
        return text
    return text[:max_length-3] + "..."

# -------------------------

"""
CLI Helper Functions for Financial RAG System

Reusable utilities for CLI operations, display formatting, and result handling.
"""

from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime
import csv
from dataclasses import dataclass, field
from rich.console import Console
from rich.table import Table as RichTable
import typer

from config.settings import settings


@dataclass
class PipelineResult:
    """Result from pipeline step execution."""
    success: bool
    message: str = ""
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


console = Console()


# ============================================================================
# METADATA EXTRACTION
# ============================================================================

def get_table_id(metadata: Dict[str, Any], fallback_index: int = 0) -> str:
    """
    Extract or generate table_id from metadata.
    
    Args:
        metadata: Metadata dictionary from search result
        fallback_index: Index to use if table_id not found
        
    Returns:
        Table ID string
    """
    table_id = metadata.get('table_id')
    if not table_id:
        doc = metadata.get('source_doc', 'unknown')
        page = metadata.get('page_no', '0')
        table_id = f"{doc}_p{page}_{fallback_index}"
    return table_id


def get_table_title(metadata: Dict[str, Any]) -> str:
    """
    Extract table title from metadata with fallback chain.
    
    Args:
        metadata: Metadata dictionary from search result
        
    Returns:
        Table title string with fallback to 'N/A'
    """
    return (
        metadata.get('table_title') or 
        metadata.get('actual_table_title') or
        metadata.get('title') or
        'N/A'
    )


# ============================================================================
# SETTINGS MANAGEMENT
# ============================================================================

def set_local_embedding_mode(local: bool) -> None:
    """
    Set embedding provider to local if flag is enabled.
    
    Args:
        local: Boolean flag indicating if local mode should be used
    """
    if local:
        console.print("[yellow]📴 Offline mode: Using local embeddings[/yellow]\n")
        settings.EMBEDDING_PROVIDER = "local"


def check_download_enabled() -> bool:
    """
    Check if downloads are enabled in settings.
    
    Returns:
        True if downloads are enabled, False otherwise
    """
    if hasattr(settings, 'DOWNLOAD_ENABLED') and not settings.DOWNLOAD_ENABLED:
        console.print("[yellow]⚠ Download disabled (DOWNLOAD_ENABLED=False in .env)[/yellow]")
        console.print("[dim]Set DOWNLOAD_ENABLED=True to enable downloads[/dim]")
        return False
    return True


# ============================================================================
# DISPLAY FORMATTING
# ============================================================================

def create_results_table(results: List[Dict[str, Any]], title: str = "Search Results") -> RichTable:
    """
    Create a standardized results table for search output.
    
    Args:
        results: List of search results with metadata
        title: Table title
        
    Returns:
        Formatted Rich table
    """
    table = RichTable(title=title)
    table.add_column("Table ID", style="dim")
    table.add_column("Table Title", style="cyan", max_width=35)
    table.add_column("Year", style="magenta")
    table.add_column("Qtr", style="yellow")
    table.add_column("Page", style="green")
    table.add_column("Score", style="blue")
    table.add_column("Content Preview", style="dim", max_width=40)
    
    for i, r in enumerate(results, 1):
        content_preview = (r['content'][:40] + '...') if len(r['content']) > 40 else r['content']
        table_title = get_table_title(r['metadata'])
        table_id = get_table_id(r['metadata'], i)
        
        table.add_row(
            str(table_id),
            str(table_title)[:35],
            str(r['metadata'].get('year', 'N/A')),
            str(r['metadata'].get('quarter', 'N/A')),
            str(r['metadata'].get('page_no', 'N/A')),
            f"{r['score']:.3f}",
            content_preview.replace('\n', ' ')
        )
    
    return table


def create_db_stats_table(db_info: Dict[str, Any]) -> RichTable:
    """
    Create database statistics table.
    
    Args:
        db_info: Database information dictionary
        
    Returns:
        Formatted Rich table with DB statistics
    """
    table = RichTable(title="Database Statistics")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")
    
    table.add_row("Total Chunks", str(db_info['total_chunks']))
    table.add_row("Unique Documents", str(db_info['unique_documents']))
    table.add_row("Unique Tables", str(db_info['unique_tables']))
    table.add_row("Years", ', '.join(map(str, db_info['years'])) or 'N/A')
    table.add_row("Quarters", ', '.join(db_info['quarters']) or 'N/A')
    
    return table


# ============================================================================
# EXPORT FUNCTIONS
# ============================================================================

def export_results_to_csv(results: List[Dict[str, Any]], query: str = "") -> Path:
    """
    Export search results to CSV with timestamp.
    
    Args:
        results: List of search results
        query: Original search query for filename
        
    Returns:
        Path to exported CSV file
    """
    output_dir = Path(settings.OUTPUT_DIR)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    query_slug = query[:20].replace(' ', '_').replace('/', '_') if query else 'search'
    csv_path = output_dir / f"{query_slug}_results_{timestamp}.csv"
    
    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['Table ID', 'Table Title', 'Year', 'Quarter', 'Source', 'Page', 'Score', 'Content'])
        
        for i, r in enumerate(results, 1):
            writer.writerow([
                get_table_id(r['metadata'], i),
                get_table_title(r['metadata']),
                r['metadata'].get('year', 'N/A'),
                r['metadata'].get('quarter', 'N/A'),
                r['metadata'].get('source_doc', r['metadata'].get('filename', 'N/A')),
                r['metadata'].get('page_no', 'N/A'),
                f"{r['score']:.4f}",
                r['content']
            ])
    
    return csv_path


# ============================================================================
# RESULT HANDLING
# ============================================================================

def handle_pipeline_result(
    result: PipelineResult, 
    success_message: Optional[str] = None,
    show_metadata: bool = True
) -> None:
    """
    Standardized result handling with exit on failure.
    
    Args:
        result: Pipeline result object
        success_message: Optional custom success message
        show_metadata: Whether to display metadata
        
    Raises:
        typer.Exit: If result indicates failure
    """
    if result.success:
        msg = success_message or result.message
        console.print(f"[green]✓ {msg}[/green]")
        if show_metadata and result.metadata:
            for key, value in result.metadata.items():
                if key in ['processed', 'total_rows', 'total_columns']:
                    console.print(f"[dim]{key}: {value}[/dim]")
    else:
        console.print(f"[red]✗ Error: {result.error}[/red]")
        raise typer.Exit(code=1)