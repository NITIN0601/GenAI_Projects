#!/usr/bin/env python3
"""
Use Docling (advanced scraper) to extract the contractual principal table
from all PDFs and create cumulative view with verification.
"""

import sys
sys.path.insert(0, '.')

from scrapers.docling_scraper import DoclingPDFScraper
from pathlib import Path
from rich.console import Console
from rich.table import Table as RichTable
from rich.panel import Panel
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
            return f"Dec 31, {year}", year, 12, f"{year}-12-31"
        else:
            if month in [1, 2, 3]:
                return f"Mar 31, {year}", year, 3, f"{year}-03-31"
            elif month in [4, 5, 6]:
                return f"Jun 30, {year}", year, 6, f"{year}-06-30"
            elif month in [7, 8, 9]:
                return f"Sep 30, {year}", year, 9, f"{year}-09-30"
            else:
                return f"Dec 31, {year}", year, 12, f"{year}-12-31"
    
    return None, None, None, None


def extract_with_docling(pdf_path):
    """Extract tables using Docling."""
    console.print(f"\n[bold cyan]Processing {Path(pdf_path).name} with Docling...[/bold cyan]")
    
    try:
        scraper = DoclingPDFScraper(pdf_path)
        document = scraper.extract_document()
        
        console.print(f"  ✓ Extracted {len(document.tables)} tables")
        
        # Search for the contractual principal table
        for table in document.tables:
            title_lower = table.original_title.lower()
            
            # Check if this is the right table
            has_contractual = "contractual" in title_lower
            has_principal = "principal" in title_lower
            has_fair_value = "fair value" in title_lower
            
            # Also check row headers
            row_texts = [rh.text.lower() for rh in table.row_headers]
            has_loans = any("loans" in rt and "receivable" in rt for rt in row_texts)
            has_nonaccrual = any("nonaccrual" in rt for rt in row_texts)
            has_borrowings = any("borrowing" in rt for rt in row_texts)
            
            # If title matches OR has all three row categories
            if (has_contractual and has_fair_value) or (has_loans and has_nonaccrual and has_borrowings):
                console.print(f"  [green]✓ Found candidate table: {table.original_title[:60]}[/green]")
                console.print(f"    Page: {table.metadata.get('page_no')}")
                console.print(f"    Row headers: {len(table.row_headers)}")
                console.print(f"    Column headers: {len(table.column_headers)}")
                
                # Extract the data
                data = extract_data_from_docling_table(table)
                
                if data:
                    console.print(f"    [green]✓ Extracted data successfully![/green]")
                    return table, data
        
        console.print(f"  [yellow]⚠ No matching table found[/yellow]")
        return None, None
        
    except Exception as e:
        console.print(f"  [red]✗ Error: {e}[/red]")
        import traceback
        traceback.print_exc()
        return None, None


def extract_data_from_docling_table(table):
    """Extract the three key values from Docling table structure."""
    data = {}
    
    # Docling gives us structured row headers
    for row_header in table.row_headers:
        text_lower = row_header.text.lower()
        canonical = row_header.canonical_label.lower() if row_header.canonical_label else ""
        
        # Find the data cells for this row
        row_cells = [cell for cell in table.data_cells if cell.row_header == row_header.text]
        
        if not row_cells:
            continue
        
        # Get the first numeric value
        value = None
        for cell in row_cells:
            if cell.parsed_value and cell.data_type in ['currency', 'number']:
                value = cell.parsed_value
                break
        
        # Categorize based on row header
        if "loans" in text_lower and "receivable" in text_lower and "nonaccrual" not in text_lower:
            data['loans'] = {
                'value': value,
                'text': row_header.text,
                'canonical': row_header.canonical_label
            }
        elif "nonaccrual" in text_lower and "loan" in text_lower:
            data['nonaccrual'] = {
                'value': value,
                'text': row_header.text,
                'canonical': row_header.canonical_label
            }
        elif "borrowing" in text_lower:
            data['borrowings'] = {
                'value': value,
                'text': row_header.text,
                'canonical': row_header.canonical_label
            }
    
    return data if len(data) >= 2 else None


def process_all_pdfs():
    """Process all PDFs with Docling."""
    pdf_dir = Path("../raw_data")
    pdf_files = sorted(pdf_dir.glob("*.pdf"))
    
    results = {}
    
    for pdf_path in pdf_files:
        period_label, year, month, period_key = extract_period_from_filename(pdf_path.name)
        
        if not period_label:
            continue
        
        table, data = extract_with_docling(str(pdf_path))
        
        if data:
            results[period_key] = {
                'period_label': period_label,
                'year': year,
                'month': month,
                'source': pdf_path.name,
                'page': table.metadata.get('page_no') if table else None,
                'table_title': table.original_title if table else None,
                'data': data,
                'table': table  # Keep for verification
            }
    
    return results


def create_cumulative_table(results):
    """Create cumulative table with verification."""
    if not results:
        console.print("[yellow]No data extracted![/yellow]")
        return None
    
    # Sort by period
    sorted_periods = sorted(results.items(), key=lambda x: x[0])
    
    console.print(f"\n[bold green]✓ Successfully extracted data from {len(results)} PDF(s)![/bold green]\n")
    
    # Create rich table
    table = RichTable(
        title="Difference Between Contractual Principal and Fair Value ($ millions)",
        show_header=True,
        header_style="bold magenta",
        show_lines=True
    )
    
    # Add columns
    table.add_column("Category", style="cyan", width=35)
    for period_key, period_data in sorted_periods:
        table.add_column(period_data['period_label'], justify="right", style="green")
    
    # Add rows
    categories = ['loans', 'nonaccrual', 'borrowings']
    category_labels = {
        'loans': 'Loans and other receivables',
        'nonaccrual': 'Nonaccrual loans',
        'borrowings': 'Borrowings'
    }
    
    for category in categories:
        row_data = [category_labels[category]]
        for period_key, period_data in sorted_periods:
            cat_data = period_data['data'].get(category, {})
            value = cat_data.get('value')
            if value:
                row_data.append(f"${value:,.0f}")
            else:
                row_data.append("—")
        
        table.add_row(*row_data)
    
    return table, sorted_periods


def create_verification_report(results):
    """Create verification report showing extraction quality."""
    console.print("\n[bold cyan]Extraction Verification Report[/bold cyan]\n")
    
    for period_key, period_data in sorted(results.items()):
        console.print(Panel(
            f"[bold]Source:[/bold] {period_data['source']}\n"
            f"[bold]Period:[/bold] {period_data['period_label']}\n"
            f"[bold]Page:[/bold] {period_data['page']}\n"
            f"[bold]Table Title:[/bold] {period_data['table_title']}\n\n"
            f"[bold]Extracted Values:[/bold]\n"
            + "\n".join([
                f"  • {period_data['data'].get(cat, {}).get('text', 'N/A')}: "
                f"${period_data['data'].get(cat, {}).get('value', 0):,.0f}"
                for cat in ['loans', 'nonaccrual', 'borrowings']
                if cat in period_data['data']
            ]),
            title=f"✓ {period_data['period_label']}",
            border_style="green"
        ))


def save_outputs(results, sorted_periods):
    """Save JSON and CSV outputs."""
    # JSON
    json_output = {
        'title': 'Difference Between Contractual Principal and Fair Value',
        'unit': 'millions USD',
        'extraction_method': 'Docling (Advanced)',
        'periods': [],
        'data': {
            'loans_and_other_receivables': [],
            'nonaccrual_loans': [],
            'borrowings': []
        },
        'sources': [],
        'verification': []
    }
    
    for period_key, period_data in sorted_periods:
        json_output['periods'].append(period_data['period_label'])
        json_output['data']['loans_and_other_receivables'].append(
            period_data['data'].get('loans', {}).get('value')
        )
        json_output['data']['nonaccrual_loans'].append(
            period_data['data'].get('nonaccrual', {}).get('value')
        )
        json_output['data']['borrowings'].append(
            period_data['data'].get('borrowings', {}).get('value')
        )
        json_output['sources'].append({
            'period': period_data['period_label'],
            'file': period_data['source'],
            'page': period_data['page'],
            'table_title': period_data['table_title']
        })
        json_output['verification'].append({
            'period': period_data['period_label'],
            'loans_text': period_data['data'].get('loans', {}).get('text'),
            'nonaccrual_text': period_data['data'].get('nonaccrual', {}).get('text'),
            'borrowings_text': period_data['data'].get('borrowings', {}).get('text')
        })
    
    json_file = "docling_cumulative_contractual_principal.json"
    with open(json_file, 'w') as f:
        json.dump(json_output, f, indent=2)
    
    console.print(f"\n[green]✓ JSON saved to {json_file}[/green]")
    
    # CSV
    csv_file = "docling_cumulative_contractual_principal.csv"
    with open(csv_file, 'w') as f:
        # Header
        f.write("Category," + ",".join([pd['period_label'] for _, pd in sorted_periods]) + "\n")
        
        # Rows
        categories = {
            'loans': 'Loans and other receivables',
            'nonaccrual': 'Nonaccrual loans',
            'borrowings': 'Borrowings'
        }
        
        for cat_key, cat_label in categories.items():
            f.write(cat_label)
            for _, pd in sorted_periods:
                value = pd['data'].get(cat_key, {}).get('value')
                f.write(f",{value if value else ''}")
            f.write("\n")
    
    console.print(f"[green]✓ CSV saved to {csv_file}[/green]")


if __name__ == "__main__":
    console.print("\n[bold cyan]{'='*70}[/bold cyan]")
    console.print("[bold cyan]Docling Advanced Extraction - Contractual Principal vs Fair Value[/bold cyan]")
    console.print(f"[bold cyan]{'='*70}[/bold cyan]")
    
    # Process all PDFs
    results = process_all_pdfs()
    
    if not results:
        console.print("\n[red]✗ No data extracted from any PDF![/red]")
        console.print("[yellow]This might indicate the table doesn't exist or has a different structure.[/yellow]")
        sys.exit(1)
    
    # Create cumulative table
    table, sorted_periods = create_cumulative_table(results)
    
    if table:
        console.print("\n")
        console.print(table)
        console.print("\n")
        
        # Verification report
        create_verification_report(results)
        
        # Save outputs
        save_outputs(results, sorted_periods)
        
        console.print(f"\n[bold green]✓ Extraction complete! Found data in {len(results)} PDF(s)[/bold green]")
