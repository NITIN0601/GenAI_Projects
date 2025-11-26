#!/usr/bin/env python3
"""
Extract contractual principal table from already-processed batch test results.
NO re-processing needed!
"""

import sys
sys.path.insert(0, '.')

from pathlib import Path
from rich.console import Console
from rich.table import Table as RichTable
import json
import re

console = Console()

# Load the batch test results (already processed!)
with open('batch_test_results.json', 'r') as f:
    results = json.load(f)

console.print("\n[bold]Extracting from Cached Results (No Re-Processing!)[/bold]")
console.print("=" * 70)

# Search each PDF's tables for the contractual principal data
contractual_data = {}

for pdf_name, tables in results.items():
    console.print(f"\n[cyan]Searching {pdf_name}...[/cyan]")
    
    for table_info in tables:
        table_text = table_info['text']
        table_lower = table_text.lower()
        
        # Look for the exact table
        if 'difference' in table_lower and 'contractual' in table_lower and 'principal' in table_lower:
            console.print(f"  [green]✓ Found in Table {table_info['table_number']}[/green]")
            
            # Extract the data
            lines = table_text.split('\n')
            data = {}
            
            for line in lines:
                line_lower = line.lower()
                
                # Extract dollar amounts
                amounts = re.findall(r'\$?\s*(\d{1,3}(?:,\d{3})*)', line)
                
                if 'loans' in line_lower and ('debt' in line_lower or 'receivable' in line_lower):
                    if 'nonaccrual' not in line_lower:
                        data['loans'] = amounts
                        console.print(f"    Loans: {amounts}")
                elif 'nonaccrual' in line_lower and 'loan' in line_lower:
                    data['nonaccrual'] = amounts
                    console.print(f"    Nonaccrual: {amounts}")
                elif 'borrowing' in line_lower:
                    data['borrowings'] = amounts
                    console.print(f"    Borrowings: {amounts}")
            
            if data:
                # Extract period from filename
                match = re.search(r'10([qk])(\d{2})(\d{2})', pdf_name.lower())
                if match:
                    doc_type, month, year = match.groups()
                    year = 2000 + int(year)
                    month = int(month)
                    
                    if doc_type == 'k':
                        period = f"Dec 31, {year}"
                    else:
                        if month in [1,2,3]:
                            period = f"Mar 31, {year}"
                        elif month in [4,5,6]:
                            period = f"Jun 30, {year}"
                        elif month in [7,8,9]:
                            period = f"Sep 30, {year}"
                    
                    contractual_data[period] = data

# Create consolidated table
if contractual_data:
    console.print(f"\n[bold green]Consolidated Table:[/bold green]\n")
    
    table = RichTable(
        title="Difference Between Contractual Principal and Fair Value ($ millions)",
        show_header=True,
        show_lines=True
    )
    
    table.add_column("Category", style="cyan", width=30)
    
    # Sort periods
    sorted_periods = sorted(contractual_data.keys())
    for period in sorted_periods:
        table.add_column(period, justify="right", style="green")
    
    # Add rows
    categories = [
        ('loans', 'Loans and other debt'),
        ('nonaccrual', 'Nonaccrual loans'),
        ('borrowings', 'Borrowings')
    ]
    
    for cat_key, cat_label in categories:
        row = [cat_label]
        for period in sorted_periods:
            values = contractual_data[period].get(cat_key, [])
            # Get first value (current period)
            row.append(f"${values[0]}" if values else "—")
        table.add_row(*row)
    
    console.print(table)
    
    # Save
    output = {
        'title': 'Difference Between Contractual Principal and Fair Value',
        'source': 'Cached batch test results (no re-processing)',
        'periods': sorted_periods,
        'data': contractual_data
    }
    
    with open('contractual_principal_from_cache.json', 'w') as f:
        json.dump(output, f, indent=2)
    
    console.print(f"\n[green]✓ Saved to contractual_principal_from_cache.json[/green]")
    console.print(f"[yellow]⚡ Extracted from cache - NO re-processing needed![/yellow]")
else:
    console.print(f"\n[red]✗ Contractual principal table not found in cached results[/red]")
