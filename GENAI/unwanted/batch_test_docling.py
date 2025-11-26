#!/usr/bin/env python3
"""
Batch test Docling extraction on 2 PDFs first.
If successful, process remaining PDFs.
"""

import sys
sys.path.insert(0, '.')

from pathlib import Path
from rich.console import Console
from rich.table import Table as RichTable
from rich.panel import Panel
from docling.document_converter import DocumentConverter
import json

console = Console()


def extract_with_docling(pdf_path: str):
    """Extract tables using raw Docling."""
    filename = Path(pdf_path).name
    console.print(f"\n[bold cyan]Processing {filename}...[/bold cyan]")
    
    try:
        converter = DocumentConverter()
        result = converter.convert(pdf_path)
        
        # Get tables
        tables = result.document.tables
        console.print(f"  [green]✓ Found {len(tables)} tables[/green]")
        
        # Extract table data
        extracted_tables = []
        for i, table in enumerate(tables, 1):
            # Get table as markdown or text
            table_text = table.export_to_markdown() if hasattr(table, 'export_to_markdown') else str(table.text)
            
            extracted_tables.append({
                'table_number': i,
                'text': table_text[:500],  # First 500 chars
                'full_text': table_text
            })
            
            # Show preview
            if i <= 3:
                console.print(f"\n  [yellow]Table {i} preview:[/yellow]")
                console.print(f"    {table_text[:200]}...")
        
        return {
            'success': True,
            'filename': filename,
            'tables_count': len(tables),
            'tables': extracted_tables
        }
        
    except Exception as e:
        console.print(f"  [red]✗ Error: {e}[/red]")
        import traceback
        traceback.print_exc()
        return {
            'success': False,
            'filename': filename,
            'error': str(e)
        }


def search_for_contractual_principal(tables_data):
    """Search for contractual principal table."""
    console.print(f"\n[cyan]Searching for contractual principal table...[/cyan]")
    
    found_tables = []
    
    for table in tables_data:
        text_lower = table['full_text'].lower()
        
        # Check for keywords
        has_contractual = 'contractual' in text_lower
        has_principal = 'principal' in text_lower
        has_fair_value = 'fair value' in text_lower
        has_loans = 'loans' in text_lower or 'loan' in text_lower
        has_borrowings = 'borrowing' in text_lower
        
        score = sum([has_contractual, has_principal, has_fair_value, has_loans, has_borrowings])
        
        if score >= 3:
            found_tables.append({
                'table_number': table['table_number'],
                'score': score,
                'text': table['full_text']
            })
    
    if found_tables:
        console.print(f"  [green]✓ Found {len(found_tables)} candidate table(s)[/green]")
        for t in found_tables:
            console.print(f"    Table {t['table_number']}: Score {t['score']}/5")
    else:
        console.print(f"  [yellow]⚠ No matching tables found[/yellow]")
    
    return found_tables


if __name__ == "__main__":
    console.print("\n[bold]Batch Testing Docling Extraction[/bold]")
    console.print("=" * 70)
    
    # Test on 2 PDFs first
    test_pdfs = [
        "../raw_data/10k1224.pdf",  # Annual report
        "../raw_data/10q0320.pdf",  # Quarterly report
    ]
    
    all_results = []
    all_contractual_tables = {}
    
    for pdf_path in test_pdfs:
        if not Path(pdf_path).exists():
            console.print(f"[red]File not found: {pdf_path}[/red]")
            continue
        
        result = extract_with_docling(pdf_path)
        all_results.append(result)
        
        if result['success'] and result['tables']:
            # Search for contractual principal table
            found = search_for_contractual_principal(result['tables'])
            if found:
                all_contractual_tables[result['filename']] = found
    
    # Summary
    console.print(f"\n[bold green]{'='*70}[/bold green]")
    console.print(f"[bold green]Batch Test Complete![/bold green]")
    console.print(f"[bold green]{'='*70}[/bold green]\n")
    
    successful = [r for r in all_results if r.get('success')]
    total_tables = sum(r.get('tables_count', 0) for r in successful)
    
    console.print(f"  PDFs Processed: {len(successful)}/{len(test_pdfs)}")
    console.print(f"  Total Tables Extracted: {total_tables}")
    console.print(f"  Contractual Principal Tables: {len(all_contractual_tables)}")
    
    # Save results
    if all_contractual_tables:
        output_file = "batch_test_results.json"
        with open(output_file, 'w') as f:
            json.dump(all_contractual_tables, f, indent=2)
        console.print(f"\n[green]✓ Results saved to {output_file}[/green]")
    
    # Decision
    if total_tables > 0:
        console.print(f"\n[bold green]✓ SUCCESS! Docling extracted {total_tables} tables[/bold green]")
        console.print(f"[yellow]Ready to process remaining 4 PDFs[/yellow]")
    else:
        console.print(f"\n[bold red]✗ FAILED! Docling extracted 0 tables[/bold red]")
        console.print(f"[yellow]Need to investigate further[/yellow]")
