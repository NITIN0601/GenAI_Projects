#!/usr/bin/env python3
"""Test pymupdf4llm Markdown conversion."""

import sys
sys.path.insert(0, '.')

from scrapers.markdown_scraper import PyMuPDF4LLMScraper
from rich.console import Console

console = Console()

console.print('\n[bold cyan]Testing pymupdf4llm Markdown conversion[/bold cyan]\n')

pdf_path = '../raw_data/10q0320.pdf'

console.print(f'Converting {pdf_path} to Markdown...\n')

scraper = PyMuPDF4LLMScraper(pdf_path)

# Convert
markdown = scraper.convert_to_markdown()

if markdown:
    console.print(f'[green]✓ Converted ({len(markdown)} chars)[/green]\n')
    
    # Save for inspection
    with open('10q0320_markdown.md', 'w') as f:
        f.write(markdown)
    console.print('[green]✓ Saved to 10q0320_markdown.md[/green]\n')
    
    # Count tables
    table_count = markdown.count('\n|')
    console.print(f'Found ~{table_count} table rows\n')
    
    # Extract tables
    console.print('[yellow]Extracting tables...[/yellow]\n')
    tables = scraper.extract_all_tables()
    
    console.print(f'[green]✓ Extracted {len(tables)} tables[/green]\n')
    
    # Find the target table
    for table in tables:
        if any(keyword in table.title.lower() for keyword in ['contractual', 'fair value', 'difference', 'principal']):
            console.print(f'[bold green]✓ FOUND: {table.title}[/bold green]\n')
            console.print(f'[bold]Headers ({len(table.headers)}):[/bold]')
            for i, h in enumerate(table.headers, 1):
                console.print(f'  {i}. [cyan]{h}[/cyan]')
            console.print(f'\n[bold]Row Elements ({len(table.rows)} rows):[/bold]')
            for i, row in enumerate(table.rows, 1):
                console.print(f'  {i}. [yellow]{row[0] if row else "empty"}[/yellow]')
            break
    else:
        console.print('[yellow]Target table not found. Showing first 5 tables:[/yellow]\n')
        for i, table in enumerate(tables[:5], 1):
            console.print(f'{i}. {table.title} ({len(table.headers)} cols, {len(table.rows)} rows)')
else:
    console.print('[red]✗ Conversion failed[/red]')
