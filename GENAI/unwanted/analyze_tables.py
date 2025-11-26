#!/usr/bin/env python3
"""Analyze table titles across all PDFs to find common tables."""

import sys
sys.path.insert(0, '.')

from scrapers import EnhancedPDFScraper
from rich.console import Console
from rich.table import Table as RichTable
from pathlib import Path
from collections import defaultdict

console = Console()

def analyze_table_titles():
    """Analyze which table titles appear across multiple PDFs."""
    
    console.print('\n[bold cyan]═══════════════════════════════════════[/bold cyan]')
    console.print('[bold cyan]  Table Title Analysis Across PDFs[/bold cyan]')
    console.print('[bold cyan]═══════════════════════════════════════[/bold cyan]\n')
    
    pdf_dir = Path('../raw_data')
    pdf_files = sorted(pdf_dir.glob('*.pdf'))
    
    # Store all tables by title
    tables_by_title = defaultdict(list)
    all_titles = []
    
    for pdf_path in pdf_files:
        filename = pdf_path.name
        console.print(f'[yellow]Analyzing {filename}...[/yellow]')
        
        scraper = EnhancedPDFScraper(str(pdf_path))
        tables = scraper.extract_all_tables()
        
        for table in tables:
            title = table.title.strip()
            if title and not title.startswith('Table_'):
                tables_by_title[title].append({
                    'file': filename,
                    'page': table.page_number,
                    'columns': len(table.headers),
                    'rows': len(table.rows),
                    'headers': table.headers,
                    'data': table.rows
                })
                all_titles.append(title)
    
    console.print()
    
    # Find tables that appear in multiple PDFs
    console.print('[bold]Tables Appearing in Multiple PDFs:[/bold]\n')
    
    recurring_tables = {title: files for title, files in tables_by_title.items() 
                       if len(files) > 1}
    
    if recurring_tables:
        recur_table = RichTable(title="Recurring Tables")
        recur_table.add_column("Table Title", style="cyan")
        recur_table.add_column("Count", style="green", justify="center")
        recur_table.add_column("Files", style="yellow")
        
        for title, occurrences in sorted(recurring_tables.items(), 
                                        key=lambda x: len(x[1]), 
                                        reverse=True)[:20]:
            files = [o['file'] for o in occurrences]
            recur_table.add_row(
                title[:60] + "..." if len(title) > 60 else title,
                str(len(occurrences)),
                ", ".join(files[:3]) + ("..." if len(files) > 3 else "")
            )
        
        console.print(recur_table)
        console.print()
    
    # Show most common table titles
    console.print('[bold]Most Common Table Titles:[/bold]\n')
    
    from collections import Counter
    title_counts = Counter(all_titles)
    
    common_table = RichTable(title="Top 15 Most Common Titles")
    common_table.add_column("Rank", style="cyan", width=6)
    common_table.add_column("Title", style="green")
    common_table.add_column("Occurrences", style="yellow", justify="center")
    
    for i, (title, count) in enumerate(title_counts.most_common(15), 1):
        common_table.add_row(
            str(i),
            title[:70] + "..." if len(title) > 70 else title,
            str(count)
        )
    
    console.print(common_table)
    console.print()
    
    # Example: Show cumulative data for a specific table
    console.print('[bold cyan]Example: Cumulative Table Data[/bold cyan]\n')
    
    # Pick a table that appears multiple times
    if recurring_tables:
        example_title = list(recurring_tables.keys())[0]
        example_occurrences = tables_by_title[example_title]
        
        console.print(f'[bold]Table:[/bold] "{example_title[:80]}"\n')
        console.print(f'[green]Found in {len(example_occurrences)} PDFs:[/green]\n')
        
        for i, occ in enumerate(example_occurrences, 1):
            console.print(f'  {i}. {occ["file"]} (Page {occ["page"]}) - {occ["columns"]} cols × {occ["rows"]} rows')
        
        console.print()
        
        # Show how cumulative data would look
        console.print('[bold]Cumulative Data Structure:[/bold]\n')
        
        total_rows = sum(o['rows'] for o in example_occurrences)
        console.print(f'  Total rows across all PDFs: [green]{total_rows}[/green]')
        console.print(f'  Total occurrences: [green]{len(example_occurrences)}[/green]')
        console.print()
        
        # Show sample of combined data
        console.print('[bold]Sample Combined Data (First 3 rows from each PDF):[/bold]\n')
        
        combined_table = RichTable(title=f"Combined: {example_title[:50]}")
        combined_table.add_column("Source", style="cyan", width=15)
        
        # Use headers from first occurrence
        if example_occurrences[0]['headers']:
            for header in example_occurrences[0]['headers'][:4]:
                combined_table.add_column(str(header)[:20], style="green")
        
        for occ in example_occurrences[:3]:  # First 3 PDFs
            for row in occ['data'][:2]:  # First 2 rows from each
                row_data = [occ['file'][:12]] + [str(cell)[:20] for cell in row[:4]]
                combined_table.add_row(*row_data)
        
        console.print(combined_table)
        console.print()
    
    # Statistics
    console.print('[bold]Statistics:[/bold]\n')
    console.print(f'  Unique table titles: {len(tables_by_title)}')
    console.print(f'  Tables in multiple PDFs: {len(recurring_tables)}')
    console.print(f'  Total table instances: {len(all_titles)}')
    console.print()
    
    return tables_by_title, recurring_tables


if __name__ == '__main__':
    tables_by_title, recurring = analyze_table_titles()
    
    # Save analysis
    import json
    
    summary = {
        'total_unique_titles': len(tables_by_title),
        'recurring_tables': len(recurring),
        'recurring_table_list': [
            {
                'title': title,
                'count': len(occurrences),
                'files': [o['file'] for o in occurrences]
            }
            for title, occurrences in recurring.items()
        ]
    }
    
    with open('table_title_analysis.json', 'w') as f:
        json.dump(summary, f, indent=2)
    
    console.print('[green]✓ Analysis saved to: table_title_analysis.json[/green]\n')
