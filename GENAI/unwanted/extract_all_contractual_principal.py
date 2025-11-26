#!/usr/bin/env python3
"""
Process all 6 PDFs with Docling and extract contractual principal table.
"""

import sys
sys.path.insert(0, '.')

from pathlib import Path
from rich.console import Console
from rich.table import Table as RichTable
from docling.document_converter import DocumentConverter
import json
import re
from datetime import datetime

console = Console()


def extract_period_from_filename(filename):
    """Extract period from PDF filename."""
    match = re.search(r'10([qk])(\d{2})(\d{2})', filename.lower())
    if match:
        doc_type, month, year = match.groups()
        month = int(month)
        year = 2000 + int(year)
        
        if doc_type == 'k':
            return f"Dec 31, {year}"
        else:
            if month in [1, 2, 3]:
                return f"Mar 31, {year}"
            elif month in [4, 5, 6]:
                return f"Jun 30, {year}"
            elif month in [7, 8, 9]:
                return f"Sep 30, {year}"
    return None


def extract_with_docling(pdf_path):
    """Extract tables using Docling."""
    filename = Path(pdf_path).name
    console.print(f"\n[cyan]Processing {filename}...[/cyan]")
    
    try:
        converter = DocumentConverter()
        result = converter.convert(pdf_path)
        
        tables = result.document.tables
        console.print(f"  Found {len(tables)} tables")
        
        # Search for contractual principal table
        for i, table in enumerate(tables, 1):
            table_md = table.export_to_markdown() if hasattr(table, 'export_to_markdown') else str(table.text)
            table_lower = table_md.lower()
            
            # Check for exact table
            if 'difference' in table_lower and 'contractual' in table_lower and 'principal' in table_lower and 'fair value' in table_lower:
                if ('loans' in table_lower or 'loan' in table_lower) and 'borrowing' in table_lower:
                    console.print(f"  [green]✓ Found contractual principal table (Table {i})[/green]")
                    return {
                        'success': True,
                        'filename': filename,
                        'period': extract_period_from_filename(filename),
                        'table_number': i,
                        'table_text': table_md
                    }
        
        console.print(f"  [yellow]⚠ Contractual principal table not found[/yellow]")
        return {'success': False, 'filename': filename}
        
    except Exception as e:
        console.print(f"  [red]✗ Error: {e}[/red]")
        return {'success': False, 'filename': filename, 'error': str(e)}


def parse_table_data(table_text):
    """Parse markdown table to extract values."""
    lines = table_text.split('\n')
    data = {}
    
    for line in lines:
        line_lower = line.lower()
        
        # Extract values (looking for $ amounts)
        amounts = re.findall(r'\$?\s*(\d{1,3}(?:,\d{3})*)', line)
        
        if 'loans' in line_lower and 'debt' in line_lower or ('loans' in line_lower and 'receivable' in line_lower):
            if 'nonaccrual' not in line_lower:
                data['loans_and_other_debt'] = amounts if amounts else []
        elif 'nonaccrual' in line_lower and 'loan' in line_lower:
            data['nonaccrual_loans'] = amounts if amounts else []
        elif 'borrowing' in line_lower:
            data['borrowings'] = amounts if amounts else []
    
    return data


if __name__ == "__main__":
    console.print("\n[bold]Processing All 6 PDFs with Docling[/bold]")
    console.print("=" * 70)
    
    pdf_files = sorted(Path("../raw_data").glob("*.pdf"))
    
    all_results = []
    
    for pdf_path in pdf_files:
        result = extract_with_docling(str(pdf_path))
        if result['success']:
            # Parse the table
            data = parse_table_data(result['table_text'])
            result['data'] = data
        all_results.append(result)
    
    # Summary
    console.print(f"\n[bold green]{'='*70}[/bold green]")
    console.print(f"[bold green]Extraction Complete![/bold green]")
    console.print(f"[bold green]{'='*70}[/bold green]\n")
    
    successful = [r for r in all_results if r.get('success')]
    console.print(f"  PDFs Processed: {len(pdf_files)}")
    console.print(f"  Tables Found: {len(successful)}")
    
    # Create consolidated table
    if successful:
        console.print(f"\n[bold]Consolidated Table:[/bold]\n")
        
        table = RichTable(show_header=True, show_lines=True)
        table.add_column("Category", style="cyan")
        
        # Add period columns
        for r in successful:
            table.add_column(r['period'], justify="right")
        
        # Add rows
        categories = ['loans_and_other_debt', 'nonaccrual_loans', 'borrowings']
        labels = {
            'loans_and_other_debt': 'Loans and other debt',
            'nonaccrual_loans': 'Nonaccrual loans',
            'borrowings': 'Borrowings'
        }
        
        for cat in categories:
            row = [labels[cat]]
            for r in successful:
                values = r.get('data', {}).get(cat, [])
                row.append(values[0] if values else "—")
            table.add_row(*row)
        
        console.print(table)
        
        # Save results
        output = {
            'extraction_date': datetime.utcnow().isoformat(),
            'tables_found': len(successful),
            'results': successful
        }
        
        with open('final_contractual_principal.json', 'w') as f:
            json.dump(output, f, indent=2, default=str)
        
        console.print(f"\n[green]✓ Results saved to final_contractual_principal.json[/green]")
