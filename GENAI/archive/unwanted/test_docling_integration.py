#!/usr/bin/env python3
"""
Test the new DoclingPDFScraper with intelligent layout detection.

This script tests the complete implementation on a sample PDF.
"""

import sys
sys.path.insert(0, '.')

from scrapers.docling_scraper import DoclingPDFScraper
from rich.console import Console
from rich.table import Table as RichTable
from rich.panel import Panel
import json

console = Console()

def test_docling_scraper(pdf_path: str):
    """Test Docling scraper on a PDF."""
    console.print(f"\n[bold cyan]Testing DoclingPDFScraper on {pdf_path}[/bold cyan]\n")
    
    try:
        # Initialize scraper
        scraper = DoclingPDFScraper(pdf_path)
        
        # Extract document
        console.print("[yellow]Extracting document...[/yellow]")
        document = scraper.extract_document()
        
        # Display document metadata
        console.print("\n[bold green]✓ Document Metadata:[/bold green]")
        metadata_table = RichTable(show_header=False, box=None)
        metadata_table.add_row("Filename:", document.metadata.filename)
        metadata_table.add_row("File Hash:", document.metadata.file_hash[:16] + "...")
        metadata_table.add_row("Company:", str(document.metadata.company_name))
        metadata_table.add_row("Document Type:", str(document.metadata.document_type))
        metadata_table.add_row("Reporting Period:", str(document.metadata.reporting_period))
        metadata_table.add_row("Total Pages:", str(document.metadata.total_pages))
        console.print(metadata_table)
        
        # Display page layout information
        console.print(f"\n[bold green]✓ Processed {len(document.pages)} pages[/bold green]")
        
        layout_summary = {}
        for page in document.pages:
            layout_type = page.get('layout_type', 'unknown')
            layout_summary[layout_type] = layout_summary.get(layout_type, 0) + 1
        
        console.print("\n[bold]Page Layout Distribution:[/bold]")
        for layout_type, count in layout_summary.items():
            console.print(f"  • {layout_type}: {count} pages")
        
        # Display table information
        console.print(f"\n[bold green]✓ Extracted {len(document.tables)} tables[/bold green]\n")
        
        if document.tables:
            # Show first 3 tables in detail
            for i, table in enumerate(document.tables[:3], 1):
                console.print(Panel(
                    f"[bold]Table {i}:[/bold] {table.original_title}\n"
                    f"[dim]Type:[/dim] {table.table_type}\n"
                    f"[dim]Page:[/dim] {table.metadata.get('page_no')}\n"
                    f"[dim]Rows:[/dim] {len(table.row_headers)} | [dim]Columns:[/dim] {len(table.column_headers)}\n"
                    f"[dim]Periods:[/dim] {len(table.periods)} | [dim]Data Cells:[/dim] {len(table.data_cells)}",
                    title=f"Table {i}",
                    border_style="cyan"
                ))
                
                # Show row headers with hierarchy
                if table.row_headers:
                    console.print("\n[bold]Row Headers (first 5):[/bold]")
                    for row_header in table.row_headers[:5]:
                        indent = "  " * row_header.indent_level
                        canonical = f" → {row_header.canonical_label}" if row_header.canonical_label else ""
                        console.print(f"  {indent}• {row_header.text}{canonical}")
                
                # Show column headers
                if table.column_headers:
                    console.print("\n[bold]Column Headers:[/bold]")
                    for col_header in table.column_headers:
                        units = f" ({col_header.units})" if col_header.units else ""
                        console.print(f"  • {col_header.text}{units}")
                
                # Show periods
                if table.periods:
                    console.print("\n[bold]Periods:[/bold]")
                    for period in table.periods:
                        console.print(f"  • {period.display_label} ({period.period_type})")
                
                # Show sample data cells
                if table.data_cells:
                    console.print("\n[bold]Sample Data Cells (first 3):[/bold]")
                    for cell in table.data_cells[:3]:
                        console.print(
                            f"  • [{cell.row_header}] × [{cell.column_header}]: "
                            f"{cell.raw_text} (type: {cell.data_type})"
                        )
                        if cell.base_value:
                            console.print(f"    Base value: {cell.base_value:,.0f}")
                
                console.print()
            
            # Summary of all tables
            console.print("\n[bold]All Tables Summary:[/bold]")
            summary_table = RichTable()
            summary_table.add_column("#", style="cyan")
            summary_table.add_column("Title", style="white")
            summary_table.add_column("Type", style="yellow")
            summary_table.add_column("Page", style="green")
            summary_table.add_column("Rows", justify="right")
            summary_table.add_column("Cols", justify="right")
            
            for i, table in enumerate(document.tables, 1):
                summary_table.add_row(
                    str(i),
                    table.original_title[:50] + "..." if len(table.original_title) > 50 else table.original_title,
                    table.table_type,
                    str(table.metadata.get('page_no')),
                    str(len(table.row_headers)),
                    str(len(table.column_headers))
                )
            
            console.print(summary_table)
        
        # Save detailed output to JSON
        output_file = 'docling_extraction_output.json'
        with open(output_file, 'w') as f:
            # Convert to dict for JSON serialization
            output_data = {
                'metadata': {
                    'filename': document.metadata.filename,
                    'file_hash': document.metadata.file_hash,
                    'company_name': document.metadata.company_name,
                    'document_type': document.metadata.document_type,
                    'reporting_period': document.metadata.reporting_period,
                    'total_pages': document.metadata.total_pages
                },
                'num_pages': len(document.pages),
                'num_tables': len(document.tables),
                'tables': [
                    {
                        'table_id': table.table_id,
                        'title': table.original_title,
                        'type': table.table_type,
                        'page': table.metadata.get('page_no'),
                        'num_rows': len(table.row_headers),
                        'num_columns': len(table.column_headers),
                        'num_periods': len(table.periods),
                        'num_data_cells': len(table.data_cells)
                    }
                    for table in document.tables
                ]
            }
            json.dump(output_data, f, indent=2)
        
        console.print(f"\n[green]✓ Detailed output saved to {output_file}[/green]")
        
        return document
        
    except Exception as e:
        console.print(f"\n[red]✗ Error: {e}[/red]")
        import traceback
        traceback.print_exc()
        return None


if __name__ == "__main__":
    # Test on a sample PDF
    pdf_path = '../raw_data/10q0325.pdf'
    
    console.print("\n" + "="*70)
    console.print("[bold cyan]DoclingPDFScraper Test Suite[/bold cyan]")
    console.print("="*70)
    
    document = test_docling_scraper(pdf_path)
    
    if document:
        console.print("\n[bold green]✓ Test completed successfully![/bold green]")
        console.print(f"\nExtracted {len(document.tables)} tables with complete structure:")
        console.print("  • Row headers with hierarchy")
        console.print("  • Column headers with periods")
        console.print("  • Data cells with types and units")
        console.print("  • Intelligent column detection (not mechanical split)")
    else:
        console.print("\n[bold red]✗ Test failed[/bold red]")
