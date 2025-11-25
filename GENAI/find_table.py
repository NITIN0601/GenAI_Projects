#!/usr/bin/env python3
"""Find and analyze the 'Difference Between Contractual Principal and Fair Value' table."""

import sys
sys.path.insert(0, '.')

from scrapers import EnhancedPDFScraper
from rich.console import Console
from rich.table import Table as RichTable
from rich.panel import Panel
from pathlib import Path

console = Console()

def find_specific_table():
    """Find the specific table across all PDFs."""
    
    console.print('\n[bold cyan]Searching for: "Difference Between Contractual Principal and Fair Value"[/bold cyan]\n')
    
    pdf_dir = Path('../raw_data')
    pdf_files = sorted(pdf_dir.glob('*.pdf'))
    
    matches = []
    
    for pdf_path in pdf_files:
        filename = pdf_path.name
        console.print(f'[yellow]Searching {filename}...[/yellow]')
        
        scraper = EnhancedPDFScraper(str(pdf_path))
        tables = scraper.extract_all_tables()
        
        for table in tables:
            if 'Difference Between Contractual Principal and Fair Value' in table.title or \
               'Contractual Principal' in table.title and 'Fair Value' in table.title:
                matches.append({
                    'file': filename,
                    'page': table.page_number,
                    'title': table.title,
                    'headers': table.headers,
                    'rows': table.rows,
                    'num_cols': len(table.headers),
                    'num_rows': len(table.rows)
                })
                console.print(f'  [green]✓ Found on page {table.page_number}[/green]')
    
    console.print()
    
    if not matches:
        console.print('[red]Table not found in any PDF[/red]')
        return
    
    console.print(f'[bold green]Found {len(matches)} instance(s) of this table[/bold green]\n')
    
    # Show details for each match
    for i, match in enumerate(matches, 1):
        console.print(f'[bold cyan]Instance {i}:[/bold cyan]')
        console.print(Panel(
            f"[bold]File:[/bold] {match['file']}\n"
            f"[bold]Page:[/bold] {match['page']}\n"
            f"[bold]Title:[/bold] {match['title']}\n"
            f"[bold]Columns:[/bold] {match['num_cols']}\n"
            f"[bold]Rows:[/bold] {match['num_rows']}",
            border_style="cyan"
        ))
        
        # Show column headers
        console.print('[bold]Column Headers (Row Elements):[/bold]')
        for j, header in enumerate(match['headers'], 1):
            console.print(f'  {j}. [green]{header}[/green]')
        console.print()
        
        # Show first few rows of data
        console.print('[bold]Sample Data (First 5 rows):[/bold]\n')
        
        data_table = RichTable(title=f"Sample from {match['file']}")
        for header in match['headers'][:6]:  # First 6 columns
            data_table.add_column(str(header)[:25], style="cyan")
        
        for row in match['rows'][:5]:  # First 5 rows
            data_table.add_row(*[str(cell)[:25] for cell in row[:6]])
        
        console.print(data_table)
        console.print('\n' + '='*80 + '\n')
    
    # Summary of all matches
    if len(matches) > 1:
        console.print('[bold cyan]Summary Across All PDFs:[/bold cyan]\n')
        
        summary_table = RichTable(title="Table Instances")
        summary_table.add_column("File", style="cyan")
        summary_table.add_column("Page", style="yellow", justify="center")
        summary_table.add_column("Columns", style="green", justify="center")
        summary_table.add_column("Rows", style="magenta", justify="center")
        
        for match in matches:
            summary_table.add_row(
                match['file'],
                str(match['page']),
                str(match['num_cols']),
                str(match['num_rows'])
            )
        
        console.print(summary_table)
        console.print()
        
        # Check if headers are consistent
        first_headers = matches[0]['headers']
        all_same = all(m['headers'] == first_headers for m in matches)
        
        if all_same:
            console.print('[green]✓ All instances have the same column structure[/green]')
        else:
            console.print('[yellow]⚠ Column structures vary across PDFs[/yellow]')
        console.print()


if __name__ == '__main__':
    find_specific_table()
