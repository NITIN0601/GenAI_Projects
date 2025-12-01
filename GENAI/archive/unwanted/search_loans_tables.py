#!/usr/bin/env python3
"""
Broader search for tables containing:
- Loans and other receivables
- Nonaccrual loans
- Borrowings
And showing difference between contractual principal and fair value
"""

import sys
sys.path.insert(0, '.')

from scrapers.pdf_scraper import EnhancedPDFScraper
from pathlib import Path
from rich.console import Console
from rich.table import Table as RichTable
import json

console = Console()

def search_for_loans_tables():
    """Search for tables containing loans, nonaccrual, and fair value concepts."""
    pdf_dir = Path("../raw_data")
    pdf_paths = sorted(pdf_dir.glob("*.pdf"))
    
    console.print(f"\n[bold cyan]Searching for tables with Loans/Nonaccrual/Fair Value...[/bold cyan]\n")
    
    all_matches = []
    
    for pdf_path in pdf_paths:
        console.print(f"\nChecking {pdf_path.name}...")
        
        try:
            scraper = EnhancedPDFScraper(str(pdf_path))
            tables = scraper.extract_all_tables()
            
            for table in tables:
                # Check table content for key terms
                table_str = (table.title + " " + str(table.rows)).lower()
                
                has_loans = "loans" in table_str and "receivables" in table_str
                has_nonaccrual = "nonaccrual" in table_str or "non-accrual" in table_str or "nonaccru" in table_str
                has_fair_value = "fair value" in table_str
                has_contractual = "contractual" in table_str or "principal" in table_str
                
                # If table has at least 2 of the 4 key concepts, it's a candidate
                score = sum([has_loans, has_nonaccrual, has_fair_value, has_contractual])
                
                if score >= 2:
                    console.print(f"  [yellow]Candidate table:[/yellow] {table.title[:60]}")
                    console.print(f"    Page: {table.page_number}")
                    console.print(f"    Loans: {has_loans}, Nonaccrual: {has_nonaccrual}, Fair Value: {has_fair_value}, Contractual: {has_contractual}")
                    console.print(f"    Score: {score}/4")
                    
                    # Check first column for these specific row headers
                    row_headers_found = []
                    for row in table.rows:
                        if row and len(row) > 0:
                            first_cell = str(row[0]).lower()
                            if "loans" in first_cell and "receivable" in first_cell:
                                row_headers_found.append("Loans and other receivables")
                            if "nonaccrual" in first_cell or "non-accrual" in first_cell:
                                row_headers_found.append("Nonaccrual loans")
                            if "borrowing" in first_cell:
                                row_headers_found.append("Borrowings")
                    
                    if row_headers_found:
                        console.print(f"    [green]✓ Found row headers: {row_headers_found}[/green]")
                    
                    all_matches.append({
                        'source': pdf_path.name,
                        'title': table.title,
                        'page': table.page_number,
                        'headers': table.headers,
                        'rows': table.rows,
                        'num_rows': len(table.rows),
                        'num_cols': len(table.headers),
                        'score': score,
                        'has_loans': has_loans,
                        'has_nonaccrual': has_nonaccrual,
                        'has_fair_value': has_fair_value,
                        'has_contractual': has_contractual,
                        'row_headers_found': row_headers_found
                    })
                    
        except Exception as e:
            console.print(f"  Error: {e}")
    
    return all_matches


if __name__ == "__main__":
    matches = search_for_loans_tables()
    
    # Sort by score (highest first)
    matches.sort(key=lambda x: x['score'], reverse=True)
    
    console.print(f"\n[bold green]Found {len(matches)} candidate table(s)![/bold green]\n")
    
    if matches:
        # Show top matches
        for i, table_data in enumerate(matches[:5], 1):
            console.print(f"\n{'='*70}")
            console.print(f"[bold]Match {i} (Score: {table_data['score']}/4)[/bold]")
            console.print(f"{'='*70}")
            console.print(f"Source: {table_data['source']}")
            console.print(f"Title: {table_data['title']}")
            console.print(f"Page: {table_data['page']}")
            console.print(f"Size: {table_data['num_rows']} rows × {table_data['num_cols']} columns")
            
            if table_data['row_headers_found']:
                console.print(f"[green]Row headers: {', '.join(table_data['row_headers_found'])}[/green]")
            
            # Show first few rows
            console.print("\nFirst 10 rows:")
            rich_table = RichTable(show_header=True, show_lines=True)
            for j, header in enumerate(table_data['headers'][:5]):
                rich_table.add_column(f"{header}"[:30])
            
            for row in table_data['rows'][:10]:
                rich_table.add_row(*[str(cell)[:30] for cell in row[:5]])
            
            console.print(rich_table)
        
        # Save all matches
        output_file = "loans_fair_value_candidates.json"
        with open(output_file, 'w') as f:
            json.dump(matches, f, indent=2, default=str)
        
        console.print(f"\n[green]✓ All {len(matches)} candidates saved to {output_file}[/green]")
