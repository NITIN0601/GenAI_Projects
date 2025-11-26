#!/usr/bin/env python3
"""Test marker-pdf on a single page."""

import sys
import os

# Add marker to PATH
os.environ['PATH'] = '/Users/nitin/Library/Python/3.9/bin:' + os.environ.get('PATH', '')

sys.path.insert(0, '.')

from scrapers.markdown_scraper import MarkdownPDFScraper
from rich.console import Console

console = Console()

console.print('\n[bold cyan]Testing marker-pdf Markdown conversion[/bold cyan]\n')

pdf_path = '../raw_data/10q0320.pdf'

console.print(f'Converting {pdf_path} to Markdown...\n')

scraper = MarkdownPDFScraper(pdf_path)

# Convert to markdown
markdown = scraper.convert_to_markdown()

if markdown:
    console.print(f'[green]✓ Converted successfully ({len(markdown)} chars)[/green]\n')
    
    # Show first 2000 chars
    console.print('[bold]First 2000 characters:[/bold]')
    console.print(markdown[:2000])
    console.print('\n...\n')
    
    # Check for tables
    table_count = markdown.count('<table')
    console.print(f'[green]Found {table_count} HTML tables in Markdown[/green]\n')
    
    # Extract tables
    console.print('[yellow]Extracting tables...[/yellow]\n')
    tables = scraper.extract_all_tables()
    
    console.print(f'[green]✓ Extracted {len(tables)} tables[/green]\n')
    
    # Show tables with "Contractual" or "Fair Value" in title
    for table in tables:
        if any(keyword in table.title for keyword in ['Contractual', 'Fair Value', 'Difference']):
            console.print(f'[bold green]Found: {table.title}[/bold green]')
            console.print(f'Headers: {table.headers}')
            console.print(f'Rows: {len(table.rows)}')
            for i, row in enumerate(table.rows[:5], 1):
                console.print(f'  {i}. {row[0] if row else "empty"}')
            break
else:
    console.print('[red]✗ Conversion failed[/red]')
