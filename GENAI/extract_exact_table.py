#!/usr/bin/env python3
"""
Extract the EXACT table format from all 6 PDFs:
- Loans and other debt
- Nonaccrual loans  
- Borrowings

Each PDF has 2 periods (current quarter and previous period).
"""

import sys
sys.path.insert(0, '.')

from scrapers.pdf_scraper import EnhancedPDFScraper
from pathlib import Path
from rich.console import Console
from rich.table import Table as RichTable
from rich.panel import Panel
import json
import re

console = Console()


def extract_table_from_pdf(pdf_path):
    """Extract the contractual principal table from a PDF."""
    filename = Path(pdf_path).name
    console.print(f"\n[cyan]Processing {filename}...[/cyan]")
    
    try:
        scraper = EnhancedPDFScraper(pdf_path)
        tables = scraper.extract_all_tables()
        
        console.print(f"  Found {len(tables)} tables total")
        
        # Search for the exact table
        for table in tables:
            # Check title
            title_lower = table.title.lower()
            if "difference" in title_lower and "contractual" in title_lower and "principal" in title_lower:
                console.print(f"  [green]✓ Found by title: {table.title[:60]}[/green]")
                return extract_data_from_table(table, filename)
            
            # Check row content for the three specific items
            row_texts = " ".join([str(row) for row in table.rows]).lower()
            has_loans_debt = ("loans" in row_texts and "debt" in row_texts) or ("loans" in row_texts and "receivable" in row_texts)
            has_nonaccrual = "nonaccrual" in row_texts
            has_borrowings = "borrowing" in row_texts
            
            if has_loans_debt and has_nonaccrual and has_borrowings:
                console.print(f"  [green]✓ Found by content on page {table.page_number}[/green]")
                console.print(f"    Title: {table.title[:60]}")
                return extract_data_from_table(table, filename)
        
        console.print(f"  [yellow]⚠ Table not found[/yellow]")
        return None
        
    except Exception as e:
        console.print(f"  [red]✗ Error: {e}[/red]")
        return None


def extract_data_from_table(table, filename):
    """Extract the three values and two periods from the table."""
    result = {
        'source': filename,
        'page': table.page_number,
        'title': table.title,
        'periods': [],
        'data': {}
    }
    
    # Extract period headers from column headers
    for header in table.headers:
        header_str = str(header)
        # Look for dates like "March 31, 2020" or "December 31, 2019"
        date_match = re.search(r'((?:March|June|September|December)\s+\d{1,2},\s*\d{4})', header_str, re.IGNORECASE)
        if date_match:
            result['periods'].append(date_match.group(1))
        elif re.search(r'(\d{1,2}/\d{1,2}/\d{4})', header_str):
            result['periods'].append(header_str)
        elif "At" in header_str or "at" in header_str:
            # Extract date after "At"
            parts = header_str.split("At")
            if len(parts) > 1:
                result['periods'].append(parts[1].strip())
    
    # Extract the three row values
    for row in table.rows:
        if not row or len(row) < 2:
            continue
        
        first_cell = str(row[0]).lower()
        
        # Loans and other debt/receivables
        if ("loans" in first_cell and "debt" in first_cell) or ("loans" in first_cell and "receivable" in first_cell):
            values = extract_numbers_from_row(row[1:])
            result['data']['loans_and_other_debt'] = {
                'label': str(row[0]),
                'values': values
            }
        
        # Nonaccrual loans
        elif "nonaccrual" in first_cell and "loan" in first_cell:
            values = extract_numbers_from_row(row[1:])
            result['data']['nonaccrual_loans'] = {
                'label': str(row[0]),
                'values': values
            }
        
        # Borrowings
        elif "borrowing" in first_cell:
            values = extract_numbers_from_row(row[1:])
            result['data']['borrowings'] = {
                'label': str(row[0]),
                'values': values
            }
    
    return result


def extract_numbers_from_row(cells):
    """Extract numeric values from row cells."""
    values = []
    for cell in cells:
        cell_str = str(cell).replace('$', '').replace(',', '').strip()
        # Handle negative numbers in parentheses
        if '(' in cell_str:
            cell_str = cell_str.replace('(', '-').replace(')', '')
        
        # Extract number
        match = re.search(r'(-?\d+(?:,?\d+)*)', cell_str)
        if match:
            try:
                value = int(match.group(1).replace(',', ''))
                values.append(value)
            except:
                values.append(None)
        else:
            values.append(None)
    
    return values


def consolidate_all_tables(all_results):
    """Consolidate all extracted tables into one."""
    console.print(f"\n[bold cyan]Consolidating {len(all_results)} tables...[/bold cyan]\n")
    
    # Collect all unique periods
    all_periods = []
    period_to_data = {}
    
    for result in all_results:
        if not result:
            continue
        
        periods = result.get('periods', [])
        data = result.get('data', {})
        
        for i, period in enumerate(periods):
            if period and period not in all_periods:
                all_periods.append(period)
                period_to_data[period] = {}
            
            # Map data to this period
            if period:
                for category, cat_data in data.items():
                    values = cat_data.get('values', [])
                    if i < len(values) and values[i] is not None:
                        period_to_data[period][category] = values[i]
    
    # Sort periods chronologically
    def parse_period(period_str):
        try:
            # Try to parse dates like "March 31, 2020"
            from dateutil import parser
            return parser.parse(period_str)
        except:
            return period_str
    
    sorted_periods = sorted(all_periods, key=parse_period)
    
    # Create consolidated table
    table = RichTable(
        title="Difference Between Contractual Principal and Fair Value ($ millions)",
        show_header=True,
        header_style="bold magenta",
        show_lines=True
    )
    
    # Add columns
    table.add_column("Category", style="cyan", width=30)
    for period in sorted_periods:
        table.add_column(period, justify="right", style="green")
    
    # Add rows
    categories = {
        'loans_and_other_debt': 'Loans and other debt',
        'nonaccrual_loans': 'Nonaccrual loans',
        'borrowings': 'Borrowings'
    }
    
    for cat_key, cat_label in categories.items():
        row_data = [cat_label]
        for period in sorted_periods:
            value = period_to_data.get(period, {}).get(cat_key)
            if value is not None:
                if value < 0:
                    row_data.append(f"$({abs(value):,})")
                else:
                    row_data.append(f"${value:,}")
            else:
                row_data.append("—")
        
        table.add_row(*row_data)
    
    return table, sorted_periods, period_to_data


def save_outputs(all_results, sorted_periods, period_to_data):
    """Save JSON and CSV outputs."""
    # JSON
    json_output = {
        'title': 'Difference Between Contractual Principal and Fair Value',
        'unit': 'millions USD',
        'periods': sorted_periods,
        'data': {
            'loans_and_other_debt': [period_to_data.get(p, {}).get('loans_and_other_debt') for p in sorted_periods],
            'nonaccrual_loans': [period_to_data.get(p, {}).get('nonaccrual_loans') for p in sorted_periods],
            'borrowings': [period_to_data.get(p, {}).get('borrowings') for p in sorted_periods]
        },
        'sources': [r for r in all_results if r]
    }
    
    json_file = "consolidated_contractual_principal.json"
    with open(json_file, 'w') as f:
        json.dump(json_output, f, indent=2, default=str)
    
    console.print(f"\n[green]✓ JSON saved to {json_file}[/green]")
    
    # CSV
    csv_file = "consolidated_contractual_principal.csv"
    with open(csv_file, 'w') as f:
        # Header
        f.write("Category," + ",".join(sorted_periods) + "\n")
        
        # Rows
        categories = {
            'loans_and_other_debt': 'Loans and other debt',
            'nonaccrual_loans': 'Nonaccrual loans',
            'borrowings': 'Borrowings'
        }
        
        for cat_key, cat_label in categories.items():
            f.write(cat_label)
            for period in sorted_periods:
                value = period_to_data.get(period, {}).get(cat_key)
                f.write(f",{value if value is not None else ''}")
            f.write("\n")
    
    console.print(f"[green]✓ CSV saved to {csv_file}[/green]")


if __name__ == "__main__":
    pdf_dir = Path("../raw_data")
    pdf_files = sorted(pdf_dir.glob("*.pdf"))
    
    console.print("\n[bold cyan]{'='*70}[/bold cyan]")
    console.print("[bold cyan]Extracting 'Difference Between Contractual Principal and Fair Value'[/bold cyan]")
    console.print("[bold cyan]{'='*70}[/bold cyan]")
    
    all_results = []
    
    # Extract from each PDF
    for pdf_path in pdf_files:
        result = extract_table_from_pdf(str(pdf_path))
        all_results.append(result)
        
        # Show individual table
        if result:
            console.print(f"\n  [bold]Extracted Data:[/bold]")
            console.print(f"    Periods: {result.get('periods', [])}")
            for cat, cat_data in result.get('data', {}).items():
                console.print(f"    {cat_data.get('label')}: {cat_data.get('values')}")
    
    # Filter out None results
    valid_results = [r for r in all_results if r]
    
    if not valid_results:
        console.print("\n[red]✗ No tables found in any PDF![/red]")
        sys.exit(1)
    
    # Consolidate
    table, sorted_periods, period_to_data = consolidate_all_tables(valid_results)
    
    console.print("\n")
    console.print(table)
    console.print("\n")
    
    # Show sources
    console.print(Panel(
        "\n".join([
            f"[cyan]{r['source']}:[/cyan] Page {r['page']}"
            for r in valid_results
        ]),
        title="Data Sources",
        border_style="blue"
    ))
    
    # Save outputs
    save_outputs(valid_results, sorted_periods, period_to_data)
    
    console.print(f"\n[bold green]✓ Successfully extracted and consolidated {len(valid_results)} tables![/bold green]")
