#!/usr/bin/env python3
"""
Search for the correct "Difference Between Contractual Principal and Fair Value" table.
Looking for table with: Loans and other receivables, Nonaccrual loans, Borrowings
"""

import sys
sys.path.insert(0, '.')

from scrapers.pdf_scraper import EnhancedPDFScraper
from pathlib import Path
from rich.console import Console
from rich.table import Table as RichTable
from rich.panel import Panel
import json

console = Console()

def search_all_pdfs_for_table():
    """Search all PDFs for tables matching the title and content."""
    pdf_dir = Path("../raw_data")
    pdf_paths = sorted(pdf_dir.glob("*.pdf"))
    
    console.print(f"\n[bold cyan]Searching {len(pdf_paths)} PDFs for correct table...[/bold cyan]\n")
    
    all_matches = []
    
    for pdf_path in pdf_paths:
        console.print(f"Checking {pdf_path.name}...")
        
        try:
            scraper = EnhancedPDFScraper(str(pdf_path))
            tables = scraper.extract_all_tables()
            
            for table in tables:
                title_lower = table.title.lower()
                
                # Check if title matches
                if "difference" in title_lower and "contractual" in title_lower and "fair value" in title_lower:
                    
                    # Check if table contains the expected row headers
                    table_text = str(table.rows).lower()
                    has_loans = "loans" in table_text or "receivables" in table_text
                    has_nonaccrual = "nonaccrual" in table_text
                    has_borrowings = "borrowings" in table_text or "borrowing" in table_text
                    
                    # Look for these specific items in row headers
                    row_headers = []
                    for row in table.rows:
                        if row and len(row) > 0:
                            first_cell = str(row[0]).lower()
                            if any(keyword in first_cell for keyword in ['loans', 'nonaccrual', 'borrowing']):
                                row_headers.append(str(row[0]))
                    
                    console.print(f"  Found table: {table.title}")
                    console.print(f"    Page: {table.page_number}")
                    console.print(f"    Has 'loans': {has_loans}")
                    console.print(f"    Has 'nonaccrual': {has_nonaccrual}")
                    console.print(f"    Has 'borrowings': {has_borrowings}")
                    console.print(f"    Rows: {len(table.rows)}, Cols: {len(table.headers)}")
                    
                    if row_headers:
                        console.print(f"    Key row headers found: {row_headers[:5]}")
                    
                    all_matches.append({
                        'source': pdf_path.name,
                        'title': table.title,
                        'page': table.page_number,
                        'headers': table.headers,
                        'rows': table.rows,
                        'num_rows': len(table.rows),
                        'num_cols': len(table.headers),
                        'has_loans': has_loans,
                        'has_nonaccrual': has_nonaccrual,
                        'has_borrowings': has_borrowings,
                        'row_headers': row_headers
                    })
                    console.print()
                    
        except Exception as e:
            console.print(f"  Error: {e}")
    
    return all_matches


def display_table(table_data):
    """Display a table in detail."""
    console.print(Panel(
        f"[bold]Source:[/bold] {table_data['source']}\n"
        f"[bold]Page:[/bold] {table_data['page']}\n"
        f"[bold]Title:[/bold] {table_data['title']}\n"
        f"[bold]Size:[/bold] {table_data['num_rows']} rows × {table_data['num_cols']} columns",
        title="Table Details",
        border_style="cyan"
    ))
    
    # Create rich table
    rich_table = RichTable(show_header=True, header_style="bold magenta", show_lines=True)
    
    # Add columns
    for i, header in enumerate(table_data['headers']):
        rich_table.add_column(f"Col {i}: {str(header)[:30]}", style="cyan")
    
    # Add all rows
    for i, row in enumerate(table_data['rows']):
        row_str = [str(cell)[:50] for cell in row]
        rich_table.add_row(*row_str)
    
    console.print(rich_table)
    console.print()


if __name__ == "__main__":
    matches = search_all_pdfs_for_table()
    
    if not matches:
        console.print("[yellow]No matching tables found![/yellow]")
    else:
        console.print(f"\n[bold green]Found {len(matches)} matching table(s)![/bold green]\n")
        
        # Display each match
        for i, table_data in enumerate(matches, 1):
            console.print(f"\n{'='*70}")
            console.print(f"[bold]Match {i}[/bold]")
            console.print(f"{'='*70}\n")
            display_table(table_data)
        
        # Save to JSON
        output_file = "correct_contractual_principal_tables.json"
        with open(output_file, 'w') as f:
            json.dump(matches, f, indent=2, default=str)
        
        console.print(f"[green]✓ Results saved to {output_file}[/green]")
