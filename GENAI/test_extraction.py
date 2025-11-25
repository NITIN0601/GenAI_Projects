#!/usr/bin/env python3
"""Quick extraction test on actual PDFs."""

import sys
sys.path.insert(0, '.')

from scrapers import EnhancedPDFScraper, MetadataExtractor
from rich.console import Console
from rich.table import Table as RichTable

console = Console()

def test_extraction():
    """Test PDF extraction on a sample file."""
    
    pdf_path = '../raw_data/10q0625.pdf'
    console.print(f'\n[bold cyan]═══════════════════════════════════════[/bold cyan]')
    console.print(f'[bold cyan]  Testing PDF Extraction[/bold cyan]')
    console.print(f'[bold cyan]═══════════════════════════════════════[/bold cyan]\n')
    console.print(f'File: {pdf_path}\n')
    
    try:
        # Extract tables
        console.print('[yellow]Extracting tables...[/yellow]')
        scraper = EnhancedPDFScraper(pdf_path)
        tables = scraper.extract_all_tables()
        
        console.print(f'[green]✓ Extracted {len(tables)} tables[/green]\n')
        
        # Display results in a table
        result_table = RichTable(title="Extracted Tables (First 10)")
        result_table.add_column("#", style="cyan", width=4)
        result_table.add_column("Page", style="magenta", width=6)
        result_table.add_column("Title", style="green")
        result_table.add_column("Cols", style="yellow", width=6)
        result_table.add_column("Rows", style="blue", width=6)
        
        for i, table in enumerate(tables[:10], 1):
            result_table.add_row(
                str(i),
                str(table.page_number),
                table.title[:60] + "..." if len(table.title) > 60 else table.title,
                str(len(table.headers)),
                str(len(table.rows))
            )
        
        console.print(result_table)
        console.print()
        
        # Test metadata extraction
        console.print('[bold cyan]Testing Metadata Extraction:[/bold cyan]\n')
        metadata_extractor = MetadataExtractor('10q0625.pdf')
        
        if tables:
            metadata = metadata_extractor.extract_metadata(
                table_title=tables[0].title,
                page_no=tables[0].page_number
            )
            
            meta_table = RichTable(title="Sample Metadata")
            meta_table.add_column("Field", style="cyan")
            meta_table.add_column("Value", style="green")
            
            meta_table.add_row("Source Doc", metadata.source_doc)
            meta_table.add_row("Year", str(metadata.year))
            meta_table.add_row("Quarter", metadata.quarter or "N/A")
            meta_table.add_row("Report Type", metadata.report_type)
            meta_table.add_row("Table Type", metadata.table_type or "N/A")
            meta_table.add_row("Page No", str(metadata.page_no))
            meta_table.add_row("Table Title", metadata.table_title[:50])
            
            console.print(meta_table)
            console.print()
        
        # Show sample table content
        if tables:
            console.print('[bold cyan]Sample Table Content:[/bold cyan]\n')
            sample_table = tables[0]
            
            content_table = RichTable(title=f"Table: {sample_table.title[:50]}")
            for header in sample_table.headers[:5]:  # First 5 columns
                content_table.add_column(str(header)[:20], style="cyan")
            
            for row in sample_table.rows[:3]:  # First 3 rows
                content_table.add_row(*[str(cell)[:20] for cell in row[:5]])
            
            console.print(content_table)
            console.print()
        
        console.print('[bold green]✓ Extraction test successful![/bold green]\n')
        return True
        
    except Exception as e:
        console.print(f'[red]✗ Error: {e}[/red]')
        import traceback
        traceback.print_exc()
        return False


if __name__ == '__main__':
    success = test_extraction()
    sys.exit(0 if success else 1)
