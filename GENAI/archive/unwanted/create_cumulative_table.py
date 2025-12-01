#!/usr/bin/env python3
"""
Create cumulative table across all PDFs showing:
- Columns: Time periods (Dec 2019, Mar 2020, Jun 2020, Sep 2020, Dec 2020, etc.)
- Rows: Loans and other receivables, Nonaccrual loans, Borrowings
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
from collections import defaultdict
from datetime import datetime

console = Console()


def extract_period_from_filename(filename):
    """Extract period from PDF filename."""
    # 10q0320.pdf -> Q1 2020 (March 2020)
    # 10q0625.pdf -> Q2 2025 (June 2025)
    # 10k1224.pdf -> FY 2024 (December 2024)
    
    match = re.search(r'10([qk])(\d{2})(\d{2})', filename.lower())
    if match:
        doc_type, month, year = match.groups()
        month = int(month)
        year = 2000 + int(year)
        
        # Map to period
        if doc_type == 'k':
            return f"Dec 31, {year}", year, 12, f"{year}-12-31"
        else:
            # Quarter mapping
            if month in [1, 2, 3]:
                return f"Mar 31, {year}", year, 3, f"{year}-03-31"
            elif month in [4, 5, 6]:
                return f"Jun 30, {year}", year, 6, f"{year}-06-30"
            elif month in [7, 8, 9]:
                return f"Sep 30, {year}", year, 9, f"{year}-09-30"
            else:
                return f"Dec 31, {year}", year, 12, f"{year}-12-31"
    
    return None, None, None, None


def find_contractual_principal_tables():
    """Find the contractual principal vs fair value table in all PDFs."""
    pdf_dir = Path("../raw_data")
    pdf_paths = sorted(pdf_dir.glob("*.pdf"))
    
    console.print(f"\n[bold cyan]Searching all PDFs for contractual principal tables...[/bold cyan]\n")
    
    results = {}
    
    for pdf_path in pdf_paths:
        period_label, year, month, period_key = extract_period_from_filename(pdf_path.name)
        
        if not period_label:
            continue
        
        console.print(f"Checking {pdf_path.name} ({period_label})...")
        
        try:
            scraper = EnhancedPDFScraper(str(pdf_path))
            tables = scraper.extract_all_tables()
            
            for table in tables:
                title_lower = table.title.lower()
                table_str = str(table.rows).lower()
                
                # Check if this is the right table
                has_contractual = "contractual" in title_lower or "contractual" in table_str
                has_fair_value = "fair value" in title_lower or "fair value" in table_str
                has_loans = "loans" in table_str and "receivable" in table_str
                has_nonaccrual = "nonaccrual" in table_str
                has_borrowings = "borrowing" in table_str
                
                # Must have all key elements
                if has_contractual and has_fair_value and has_loans and has_nonaccrual and has_borrowings:
                    console.print(f"  [green]✓ Found table: {table.title[:60]}[/green]")
                    console.print(f"    Page: {table.page_number}")
                    
                    # Extract the three values
                    data = extract_values_from_table(table)
                    
                    if data:
                        results[period_key] = {
                            'period_label': period_label,
                            'year': year,
                            'month': month,
                            'source': pdf_path.name,
                            'page': table.page_number,
                            'data': data
                        }
                        console.print(f"    [green]✓ Extracted: Loans=${data.get('loans', 'N/A')}, Nonaccrual=${data.get('nonaccrual', 'N/A')}, Borrowings=${data.get('borrowings', 'N/A')}[/green]")
                        break
                    
        except Exception as e:
            console.print(f"  [red]Error: {e}[/red]")
    
    return results


def extract_values_from_table(table):
    """Extract the three key values from the table."""
    data = {}
    
    for row in table.rows:
        if not row or len(row) < 2:
            continue
        
        first_cell = str(row[0]).lower()
        
        # Look for the three categories
        if "loans" in first_cell and "receivable" in first_cell and "nonaccrual" not in first_cell:
            # Extract value from second column
            value = extract_number(str(row[1]) if len(row) > 1 else "")
            if value:
                data['loans'] = value
        
        elif "nonaccrual" in first_cell and "loan" in first_cell:
            value = extract_number(str(row[1]) if len(row) > 1 else "")
            if value:
                data['nonaccrual'] = value
        
        elif "borrowing" in first_cell:
            value = extract_number(str(row[1]) if len(row) > 1 else "")
            if value:
                data['borrowings'] = value
    
    return data if len(data) >= 2 else None


def extract_number(text):
    """Extract number from text like '$ 10,207' or '7,719'."""
    # Remove $ and commas, extract first number
    cleaned = text.replace('$', '').replace(',', '').strip()
    match = re.search(r'(\d+)', cleaned)
    if match:
        return int(match.group(1))
    return None


def create_cumulative_table(results):
    """Create cumulative table with periods as columns."""
    if not results:
        console.print("[yellow]No data found![/yellow]")
        return None
    
    # Sort by period
    sorted_periods = sorted(results.items(), key=lambda x: x[0])
    
    # Create rich table
    table = RichTable(title="Difference Between Contractual Principal and Fair Value ($ millions)", 
                      show_header=True, header_style="bold magenta", show_lines=True)
    
    # Add columns
    table.add_column("Category", style="cyan", width=30)
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
            value = period_data['data'].get(category)
            if value:
                row_data.append(f"${value:,}")
            else:
                row_data.append("—")
        
        table.add_row(*row_data)
    
    return table, sorted_periods


def create_json_output(results):
    """Create JSON output for programmatic use."""
    sorted_periods = sorted(results.items(), key=lambda x: x[0])
    
    output = {
        'title': 'Difference Between Contractual Principal and Fair Value',
        'unit': 'millions USD',
        'periods': [],
        'data': {
            'loans_and_other_receivables': [],
            'nonaccrual_loans': [],
            'borrowings': []
        },
        'sources': []
    }
    
    for period_key, period_data in sorted_periods:
        output['periods'].append(period_data['period_label'])
        output['data']['loans_and_other_receivables'].append(period_data['data'].get('loans'))
        output['data']['nonaccrual_loans'].append(period_data['data'].get('nonaccrual'))
        output['data']['borrowings'].append(period_data['data'].get('borrowings'))
        output['sources'].append({
            'period': period_data['period_label'],
            'file': period_data['source'],
            'page': period_data['page']
        })
    
    return output


if __name__ == "__main__":
    # Extract data from all PDFs
    results = find_contractual_principal_tables()
    
    if not results:
        console.print("\n[red]No tables found![/red]")
        sys.exit(1)
    
    console.print(f"\n[bold green]Found data in {len(results)} PDF(s)![/bold green]\n")
    
    # Create cumulative table
    table, sorted_periods = create_cumulative_table(results)
    
    if table:
        console.print("\n")
        console.print(table)
        console.print("\n")
        
        # Show sources
        console.print(Panel(
            "\n".join([
                f"[cyan]{pd['period_label']}:[/cyan] {pd['source']} (page {pd['page']})"
                for _, pd in sorted_periods
            ]),
            title="Data Sources",
            border_style="blue"
        ))
        
        # Save to JSON
        json_output = create_json_output(results)
        output_file = "cumulative_contractual_principal_fair_value.json"
        with open(output_file, 'w') as f:
            json.dump(json_output, f, indent=2)
        
        console.print(f"\n[green]✓ Data saved to {output_file}[/green]")
        
        # Create CSV for Excel
        csv_file = "cumulative_contractual_principal_fair_value.csv"
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
                    value = pd['data'].get(cat_key)
                    f.write(f",{value if value else ''}")
                f.write("\n")
        
        console.print(f"[green]✓ CSV saved to {csv_file}[/green]")
