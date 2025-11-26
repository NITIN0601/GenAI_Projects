#!/usr/bin/env python3
"""Quick test of the fixed extraction."""

import sys
sys.path.insert(0, '.')

from scrapers import EnhancedPDFScraper
from rich.console import Console

console = Console()

# Test on just one PDF
pdf_path = '../raw_data/10q0320.pdf'
console.print(f'\n[bold]Testing: {pdf_path}[/bold]\n')

scraper = EnhancedPDFScraper(pdf_path)

# Extract from page 57 only (where the table is)
tables = scraper.extract_all_tables(pages=[56])  # 0-indexed, so page 57 = index 56

console.print(f'Found {len(tables)} tables on page 57\n')

for table in tables:
    if 'Contractual Principal' in table.title or 'Fair Value' in table.title:
        console.print(f'[green]✓ Found table: {table.title}[/green]\n')
        console.print(f'Headers ({len(table.headers)}):')
        for i, h in enumerate(table.headers, 1):
            console.print(f'  {i}. {h}')
        console.print(f'\nRows ({len(table.rows)}):')
        for i, row in enumerate(table.rows[:5], 1):
            console.print(f'  {i}. {row[0] if row else "empty"}')
        break
