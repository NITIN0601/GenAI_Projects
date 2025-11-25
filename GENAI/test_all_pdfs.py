#!/usr/bin/env python3
"""Test extraction on all PDFs in raw_data."""

import sys
sys.path.insert(0, '.')

from scrapers import EnhancedPDFScraper, MetadataExtractor
from rich.console import Console
from rich.table import Table as RichTable
from pathlib import Path

console = Console()

def test_all_pdfs():
    """Test extraction on all PDFs."""
    
    console.print('\n[bold cyan]═══════════════════════════════════════[/bold cyan]')
    console.print('[bold cyan]  Testing All PDFs[/bold cyan]')
    console.print('[bold cyan]═══════════════════════════════════════[/bold cyan]\n')
    
    pdf_dir = Path('../raw_data')
    pdf_files = sorted(pdf_dir.glob('*.pdf'))
    
    if not pdf_files:
        console.print('[red]No PDF files found![/red]')
        return False
    
    results = []
    
    for pdf_path in pdf_files:
        filename = pdf_path.name
        console.print(f'[yellow]Processing {filename}...[/yellow]')
        
        try:
            scraper = EnhancedPDFScraper(str(pdf_path))
            tables = scraper.extract_all_tables()
            
            # Extract metadata
            metadata_extractor = MetadataExtractor(filename)
            if tables:
                metadata = metadata_extractor.extract_metadata(
                    table_title=tables[0].title,
                    page_no=tables[0].page_number
                )
                
                results.append({
                    'filename': filename,
                    'tables': len(tables),
                    'year': metadata.year,
                    'quarter': metadata.quarter or 'N/A',
                    'report_type': metadata.report_type,
                    'success': True
                })
                console.print(f'[green]✓ {len(tables)} tables extracted[/green]')
            else:
                results.append({
                    'filename': filename,
                    'tables': 0,
                    'year': 'N/A',
                    'quarter': 'N/A',
                    'report_type': 'N/A',
                    'success': False
                })
                console.print('[yellow]⚠ No tables found[/yellow]')
                
        except Exception as e:
            console.print(f'[red]✗ Error: {e}[/red]')
            results.append({
                'filename': filename,
                'tables': 0,
                'year': 'N/A',
                'quarter': 'N/A',
                'report_type': 'N/A',
                'success': False
            })
    
    # Display summary
    console.print('\n[bold cyan]Extraction Summary:[/bold cyan]\n')
    
    summary_table = RichTable(title="PDF Extraction Results")
    summary_table.add_column("File", style="cyan")
    summary_table.add_column("Tables", style="green", justify="right")
    summary_table.add_column("Year", style="yellow", justify="center")
    summary_table.add_column("Quarter", style="magenta", justify="center")
    summary_table.add_column("Type", style="blue", justify="center")
    summary_table.add_column("Status", style="green", justify="center")
    
    for result in results:
        status = "✓" if result['success'] else "✗"
        summary_table.add_row(
            result['filename'],
            str(result['tables']),
            str(result['year']),
            result['quarter'],
            result['report_type'],
            status
        )
    
    console.print(summary_table)
    
    # Statistics
    total_tables = sum(r['tables'] for r in results)
    successful = sum(1 for r in results if r['success'])
    
    console.print(f'\n[bold]Statistics:[/bold]')
    console.print(f'  Files processed: {len(results)}')
    console.print(f'  Successful: {successful}/{len(results)}')
    console.print(f'  Total tables: {total_tables}')
    console.print(f'  Average tables/file: {total_tables/len(results):.1f}')
    console.print()
    
    return all(r['success'] for r in results)


if __name__ == '__main__':
    success = test_all_pdfs()
    sys.exit(0 if success else 1)
