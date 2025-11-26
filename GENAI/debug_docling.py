#!/usr/bin/env python3
"""
Debug Docling extraction - test raw Docling output.
"""

import sys
sys.path.insert(0, '.')

from pathlib import Path
from rich.console import Console
from docling.document_converter import DocumentConverter

console = Console()


def test_raw_docling(pdf_path: str):
    """Test raw Docling output to see if it finds tables."""
    filename = Path(pdf_path).name
    console.print(f"\n[bold cyan]Testing {filename} with raw Docling...[/bold cyan]")
    
    try:
        # Use Docling directly
        converter = DocumentConverter()
        result = converter.convert(pdf_path)
        
        console.print(f"  [green]✓ Conversion successful[/green]")
        console.print(f"  Pages: {len(result.document.pages)}")
        
        # Check for tables
        tables = result.document.tables
        console.print(f"  [yellow]Tables found: {len(tables)}[/yellow]")
        
        if tables:
            # Show first few tables
            for i, table in enumerate(tables[:5], 1):
                console.print(f"\n  [bold]Table {i}:[/bold]")
                console.print(f"    Text preview: {str(table.text)[:200]}...")
                
                # Try to get table data
                if hasattr(table, 'data'):
                    console.print(f"    Has data attribute: Yes")
                if hasattr(table, 'cells'):
                    console.print(f"    Has cells attribute: Yes")
                if hasattr(table, 'grid'):
                    console.print(f"    Has grid attribute: Yes")
                
                # Show all attributes
                console.print(f"    Attributes: {dir(table)}")
        else:
            console.print("  [red]No tables found by Docling![/red]")
        
        return result
        
    except Exception as e:
        console.print(f"  [red]Error: {e}[/red]")
        import traceback
        traceback.print_exc()
        return None


if __name__ == "__main__":
    # Test on one PDF first
    pdf_path = "../raw_data/10k1224.pdf"
    
    console.print("\n[bold]Testing Raw Docling Output[/bold]")
    console.print("=" * 70)
    
    result = test_raw_docling(pdf_path)
    
    if result:
        console.print(f"\n[bold green]✓ Docling conversion successful[/bold green]")
        console.print(f"[yellow]Tables found: {len(result.document.tables)}[/yellow]")
    else:
        console.print(f"\n[bold red]✗ Docling conversion failed[/bold red]")
