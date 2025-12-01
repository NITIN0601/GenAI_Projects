#!/usr/bin/env python3
"""
Debug script to see ALL tables extracted from each PDF
and find why we're missing the contractual principal table.
"""

import sys
sys.path.insert(0, '.')

from scrapers.pdf_scraper import EnhancedPDFScraper
from pathlib import Path
from rich.console import Console
from rich.table import Table as RichTable
import json

console = Console()

def debug_pdf_extraction(pdf_path):
    """Extract and show ALL tables from a PDF."""
    console.print(f"\n[bold cyan]{'='*70}[/bold cyan]")
    console.print(f"[bold cyan]Debugging: {Path(pdf_path).name}[/bold cyan]")
    console.print(f"[bold cyan]{'='*70}[/bold cyan]\n")
    
    try:
        scraper = EnhancedPDFScraper(pdf_path)
        tables = scraper.extract_all_tables()
        
        console.print(f"[green]✓ Extracted {len(tables)} tables total[/green]\n")
        
        # Search for tables containing our keywords
        candidates = []
        
        for i, table in enumerate(tables, 1):
            title_lower = table.title.lower()
            
            # Get first few rows as text
            rows_text = ""
            for row in table.rows[:10]:
                rows_text += " ".join([str(cell) for cell in row]) + " "
            rows_text = rows_text.lower()
            
            # Check for keywords
            has_contractual = "contractual" in title_lower or "contractual" in rows_text
            has_principal = "principal" in title_lower or "principal" in rows_text
            has_fair_value = "fair value" in title_lower or "fair value" in rows_text
            has_loans = "loans" in rows_text or "loan" in rows_text
            has_receivables = "receivables" in rows_text or "receivable" in rows_text
            has_nonaccrual = "nonaccrual" in rows_text or "non-accrual" in rows_text
            has_borrowings = "borrowings" in rows_text or "borrowing" in rows_text
            
            # Score the table
            score = sum([
                has_contractual, has_principal, has_fair_value,
                has_loans, has_receivables, has_nonaccrual, has_borrowings
            ])
            
            if score >= 3:  # If it has at least 3 keywords, it's a candidate
                candidates.append({
                    'index': i,
                    'table': table,
                    'score': score,
                    'keywords': {
                        'contractual': has_contractual,
                        'principal': has_principal,
                        'fair_value': has_fair_value,
                        'loans': has_loans,
                        'receivables': has_receivables,
                        'nonaccrual': has_nonaccrual,
                        'borrowings': has_borrowings
                    }
                })
        
        if candidates:
            console.print(f"[yellow]Found {len(candidates)} candidate table(s) with relevant keywords:[/yellow]\n")
            
            for candidate in sorted(candidates, key=lambda x: x['score'], reverse=True):
                table = candidate['table']
                console.print(f"[bold]Table {candidate['index']} (Score: {candidate['score']}/7)[/bold]")
                console.print(f"  Title: {table.title[:80]}")
                console.print(f"  Page: {table.page_number}")
                console.print(f"  Size: {len(table.rows)} rows × {len(table.headers)} columns")
                console.print(f"  Keywords: {', '.join([k for k, v in candidate['keywords'].items() if v])}")
                
                # Show first 5 rows
                console.print(f"\n  First 5 rows:")
                for j, row in enumerate(table.rows[:5], 1):
                    row_str = " | ".join([str(cell)[:30] for cell in row[:4]])
                    console.print(f"    Row {j}: {row_str}")
                
                console.print()
        else:
            console.print("[red]No candidate tables found with keywords![/red]")
            console.print("\n[yellow]Showing all table titles:[/yellow]\n")
            for i, table in enumerate(tables[:20], 1):
                console.print(f"  {i}. {table.title[:80]} (page {table.page_number})")
        
        return candidates
        
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        import traceback
        traceback.print_exc()
        return []


if __name__ == "__main__":
    pdf_dir = Path("../raw_data")
    pdf_files = [
        "10q0320.pdf",  # Q1 2020
        "10q0324.pdf",  # Q1 2024
        "10q0325.pdf",  # Q1 2025
        "10q0625.pdf",  # Q2 2025
        "10q0925.pdf",  # Q3 2025
        "10k1224.pdf",  # Annual 2024
    ]
    
    all_results = {}
    
    for pdf_file in pdf_files:
        pdf_path = pdf_dir / pdf_file
        if pdf_path.exists():
            candidates = debug_pdf_extraction(str(pdf_path))
            all_results[pdf_file] = candidates
        else:
            console.print(f"[red]File not found: {pdf_file}[/red]")
    
    # Summary
    console.print(f"\n[bold cyan]{'='*70}[/bold cyan]")
    console.print(f"[bold cyan]SUMMARY[/bold cyan]")
    console.print(f"[bold cyan]{'='*70}[/bold cyan]\n")
    
    for pdf_file, candidates in all_results.items():
        if candidates:
            console.print(f"[green]✓ {pdf_file}: {len(candidates)} candidate(s) found[/green]")
        else:
            console.print(f"[red]✗ {pdf_file}: No candidates found[/red]")
