#!/usr/bin/env python3
"""
Parallel PDF processor for faster extraction.
Uses multiprocessing to process multiple PDFs simultaneously.
"""

import sys
sys.path.insert(0, '.')

from scrapers.pdf_scraper import EnhancedPDFScraper  # Use faster pdfplumber scraper
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed
from typing import List, Dict, Any
import time
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn
from rich.table import Table as RichTable
from rich.panel import Panel
import json

console = Console()


def process_single_pdf(pdf_path: str) -> Dict[str, Any]:
    """Process a single PDF and return results."""
    try:
        scraper = EnhancedPDFScraper(pdf_path)
        tables = scraper.extract_all_tables()
        
        return {
            'filename': Path(pdf_path).name,
            'success': True,
            'num_tables': len(tables),
            'tables': [
                {
                    'title': table.title,
                    'page': table.page_number,
                    'rows': len(table.rows),
                    'columns': len(table.headers),
                    'data': {
                        'headers': table.headers,
                        'rows': table.rows
                    }
                }
                for table in tables
            ],
            'error': None
        }
    except Exception as e:
        return {
            'filename': Path(pdf_path).name,
            'success': False,
            'num_tables': 0,
            'tables': [],
            'error': str(e)
        }


def process_pdfs_parallel(pdf_paths: List[str], max_workers: int = 3) -> List[Dict[str, Any]]:
    """
    Process multiple PDFs in parallel.
    
    Args:
        pdf_paths: List of PDF file paths
        max_workers: Maximum number of parallel workers
    
    Returns:
        List of results for each PDF
    """
    results = []
    
    console.print(f"\n[bold cyan]Processing {len(pdf_paths)} PDFs in parallel (max {max_workers} workers)...[/bold cyan]\n")
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeElapsedColumn(),
        console=console
    ) as progress:
        
        task = progress.add_task("[cyan]Processing PDFs...", total=len(pdf_paths))
        
        with ProcessPoolExecutor(max_workers=max_workers) as executor:
            # Submit all jobs
            future_to_pdf = {
                executor.submit(process_single_pdf, pdf_path): pdf_path
                for pdf_path in pdf_paths
            }
            
            # Collect results as they complete
            for future in as_completed(future_to_pdf):
                pdf_path = future_to_pdf[future]
                try:
                    result = future.result()
                    results.append(result)
                    
                    if result['success']:
                        console.print(f"  ✓ {result['filename']}: {result['num_tables']} tables")
                    else:
                        console.print(f"  ✗ {result['filename']}: {result['error']}")
                    
                    progress.update(task, advance=1)
                    
                except Exception as e:
                    console.print(f"  ✗ {Path(pdf_path).name}: {e}")
                    results.append({
                        'filename': Path(pdf_path).name,
                        'success': False,
                        'num_tables': 0,
                        'tables': [],
                        'error': str(e)
                    })
                    progress.update(task, advance=1)
    
    return results


def find_table_by_title(results: List[Dict[str, Any]], search_title: str) -> List[Dict[str, Any]]:
    """
    Find tables matching a specific title across all PDFs.
    
    Args:
        results: Results from parallel processing
        search_title: Title to search for (case-insensitive, partial match)
    
    Returns:
        List of matching tables with source information
    """
    matching_tables = []
    search_lower = search_title.lower()
    
    for result in results:
        if not result['success']:
            continue
        
        for table in result['tables']:
            if search_lower in table['title'].lower():
                matching_tables.append({
                    'source': result['filename'],
                    'title': table['title'],
                    'page': table['page'],
                    'headers': table['data']['headers'],
                    'rows': table['data']['rows'],
                    'num_rows': table['rows'],
                    'num_cols': table['columns']
                })
    
    return matching_tables


def display_table_results(matching_tables: List[Dict[str, Any]], search_title: str):
    """Display matching tables in a nice format."""
    
    if not matching_tables:
        console.print(f"\n[yellow]No tables found matching: '{search_title}'[/yellow]")
        return
    
    console.print(f"\n[bold green]Found {len(matching_tables)} table(s) matching: '{search_title}'[/bold green]\n")
    
    for i, table_data in enumerate(matching_tables, 1):
        console.print(Panel(
            f"[bold]Source:[/bold] {table_data['source']}\n"
            f"[bold]Page:[/bold] {table_data['page']}\n"
            f"[bold]Title:[/bold] {table_data['title']}\n"
            f"[bold]Size:[/bold] {table_data['num_rows']} rows × {table_data['num_cols']} columns",
            title=f"Table {i}",
            border_style="cyan"
        ))
        
        # Create rich table
        rich_table = RichTable(show_header=True, header_style="bold magenta")
        
        # Add columns
        for header in table_data['headers']:
            rich_table.add_column(str(header), style="cyan")
        
        # Add rows (limit to first 10 for display)
        for row in table_data['rows'][:10]:
            rich_table.add_row(*[str(cell) for cell in row])
        
        if len(table_data['rows']) > 10:
            console.print(f"\n[dim]Showing first 10 of {len(table_data['rows'])} rows[/dim]")
        
        console.print(rich_table)
        console.print()


def save_results(matching_tables: List[Dict[str, Any]], output_file: str):
    """Save results to JSON file."""
    with open(output_file, 'w') as f:
        json.dump(matching_tables, f, indent=2)
    console.print(f"[green]✓ Results saved to {output_file}[/green]")


if __name__ == "__main__":
    # Find all PDFs
    pdf_dir = Path("../raw_data")
    pdf_paths = sorted(pdf_dir.glob("*.pdf"))
    
    if not pdf_paths:
        console.print("[red]No PDFs found in ../raw_data[/red]")
        sys.exit(1)
    
    console.print(f"\n[bold]Found {len(pdf_paths)} PDFs:[/bold]")
    for pdf in pdf_paths:
        console.print(f"  • {pdf.name}")
    
    # Process PDFs in parallel
    start_time = time.time()
    results = process_pdfs_parallel([str(p) for p in pdf_paths], max_workers=3)
    elapsed = time.time() - start_time
    
    # Summary
    successful = sum(1 for r in results if r['success'])
    total_tables = sum(r['num_tables'] for r in results if r['success'])
    
    console.print(f"\n[bold green]Processing Complete![/bold green]")
    console.print(f"  Time: {elapsed:.1f}s")
    console.print(f"  Successful: {successful}/{len(results)}")
    console.print(f"  Total tables: {total_tables}")
    
    # Search for specific table
    search_title = "Difference Between Contractual Principal and Fair Value"
    console.print(f"\n[bold cyan]Searching for: '{search_title}'...[/bold cyan]")
    
    matching_tables = find_table_by_title(results, search_title)
    
    # Display results
    display_table_results(matching_tables, search_title)
    
    # Save to file
    if matching_tables:
        output_file = "contractual_principal_fair_value_tables.json"
        save_results(matching_tables, output_file)
        
        console.print(f"\n[bold]Summary:[/bold]")
        console.print(f"  • Found in {len(matching_tables)} PDF(s)")
        console.print(f"  • Results saved to {output_file}")
        console.print(f"  • Use this data for analysis or reporting")
