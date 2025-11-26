#!/usr/bin/env python3
"""Test PyMuPDF scraper on the complex table."""

import sys
sys.path.insert(0, '.')

from scrapers.pymupdf_scraper import PyMuPDFScraper
from rich.console import Console
from rich.table import Table as RichTable

console = Console()

console.print('\n[bold cyan]Testing PyMuPDF on "Difference Between Contractual Principal and Fair Value"[/bold cyan]\n')

# Test on 10q0320.pdf page 57
pdf_path = '../raw_data/10q0320.pdf'

with PyMuPDFScraper(pdf_path) as scraper:
    # Extract from page 57 (index 56)
    tables = scraper.extract_all_tables(pages=[56])
    
    console.print(f'[green]Found {len(tables)} tables on page 57[/green]\n')
    
    for table in tables:
        if 'Contractual' in table.title or 'Fair Value' in table.title or 'Difference' in table.title:
            console.print(f'[bold green]✓ Found: {table.title}[/bold green]\n')
            
            # Show headers
            console.print(f'[bold]Column Headers ({len(table.headers)}):[/bold]')
            for i, header in enumerate(table.headers, 1):
                console.print(f'  {i}. [cyan]{header}[/cyan]')
            console.print()
            
            # Show row elements
            console.print(f'[bold]Row Elements ({len(table.rows)} rows):[/bold]')
            for i, row in enumerate(table.rows, 1):
                first_col = row[0] if row else 'empty'
                console.print(f'  {i}. [yellow]{first_col}[/yellow]')
            console.print()
            
            # Show full table
            if len(table.headers) > 0 and len(table.rows) > 0:
                display_table = RichTable(title=table.title[:60])
                
                # Add columns (limit to 6 for display)
                for header in table.headers[:6]:
                    display_table.add_column(str(header)[:25], style="cyan")
                
                # Add rows
                for row in table.rows:
                    display_table.add_row(*[str(cell)[:25] for cell in row[:6]])
                
                console.print(display_table)
            
            break
    else:
        console.print('[yellow]Table not found. Showing all tables:[/yellow]\n')
        for i, table in enumerate(tables, 1):
            console.print(f'{i}. {table.title} ({len(table.headers)} cols, {len(table.rows)} rows)')
