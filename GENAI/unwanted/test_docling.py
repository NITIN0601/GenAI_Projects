#!/usr/bin/env python3
"""Test Docling on the complex table."""

import sys
sys.path.insert(0, '.')

from docling.document_converter import DocumentConverter
from rich.console import Console
from rich.table import Table as RichTable
import json

console = Console()

console.print('\n[bold cyan]Testing Docling PDF Extraction[/bold cyan]\n')

pdf_path = '../raw_data/10q0320.pdf'

console.print(f'Converting {pdf_path}...\n')

try:
    converter = DocumentConverter()
    result = converter.convert(pdf_path)
    
    console.print(f'[green]✓ Conversion successful[/green]\n')
    
    # Get document
    doc = result.document
    
    # Export to dict to see structure
    doc_dict = doc.export_to_dict()
    
    # Save full output
    with open('docling_output.json', 'w') as f:
        json.dump(doc_dict, f, indent=2)
    console.print('[green]✓ Saved to docling_output.json[/green]\n')
    
    # Count tables
    tables = [item for item in doc.iterate_items() if item.label == 'table']
    console.print(f'[green]Found {len(tables)} tables[/green]\n')
    
    # Find target table on page 57
    console.print('[yellow]Looking for table on page 57...[/yellow]\n')
    
    for table in tables:
        # Check page number
        if hasattr(table, 'prov') and table.prov:
            page_no = table.prov[0].page_no if table.prov[0].page_no else 0
            
            if page_no == 57:
                console.print(f'[bold green]✓ Found table on page 57![/bold green]\n')
                
                # Show table details
                console.print(f'[bold]Caption:[/bold] {table.caption if hasattr(table, "caption") else "N/A"}')
                console.print(f'[bold]Page:[/bold] {page_no}')
                
                # Show table data structure
                if hasattr(table, 'data'):
                    console.print(f'\n[bold]Table Data Structure:[/bold]')
                    console.print(f'Type: {type(table.data)}')
                    console.print(f'Content: {str(table.data)[:500]}...\n')
                
                # Try to access table in different ways
                console.print('[bold]Attempting to extract table structure...[/bold]\n')
                
                # Check what attributes the table has
                console.print(f'Table attributes: {dir(table)[:20]}...\n')
                
                break
    else:
        console.print('[yellow]Table on page 57 not found. Showing first 3 tables:[/yellow]\n')
        for i, table in enumerate(tables[:3], 1):
            page_no = table.prov[0].page_no if hasattr(table, 'prov') and table.prov else 0
            caption = table.caption if hasattr(table, 'caption') else 'No caption'
            console.print(f'{i}. Page {page_no}: {caption}')
    
except Exception as e:
    console.print(f'[red]✗ Error: {e}[/red]')
    import traceback
    traceback.print_exc()
