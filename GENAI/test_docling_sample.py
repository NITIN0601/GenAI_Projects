#!/usr/bin/env python3
"""
Test Docling extraction on sample files (1 10-K and 1 10-Q)
"""

from docling.document_converter import DocumentConverter
from pathlib import Path
import json
from rich.console import Console
from rich.table import Table as RichTable

console = Console()

def test_extraction(pdf_path: Path):
    """Test Docling extraction on a single PDF."""
    console.print(f"\n[bold cyan]Testing: {pdf_path.name}[/bold cyan]")
    console.print("="*70)
    
    # Convert PDF
    converter = DocumentConverter()
    result = converter.convert(pdf_path)
    doc = result.document
    
    # Basic stats
    console.print(f"\n[bold]Document Statistics:[/bold]")
    console.print(f"  Total Pages: {len(doc.pages)}")
    
    # Count different element types
    tables = list(doc.tables)
    texts = list(doc.texts)
    
    console.print(f"  Total Tables: {len(tables)}")
    console.print(f"  Total Text Elements: {len(texts)}")
    
    # Show first 5 tables
    console.print(f"\n[bold]First 5 Tables:[/bold]")
    table_display = RichTable(show_header=True, header_style="bold magenta")
    table_display.add_column("#", style="cyan", width=4)
    table_display.add_column("Caption", style="green")
    table_display.add_column("Rows", justify="right", style="yellow", width=6)
    table_display.add_column("Cols", justify="right", style="yellow", width=6)
    table_display.add_column("Page", justify="right", style="blue", width=6)
    
    for i, table in enumerate(tables[:5]):
        caption = getattr(table, 'caption', 'No caption')
        if caption and len(caption) > 60:
            caption = caption[:57] + "..."
        
        table_display.add_row(
            str(i+1),
            caption or "No caption",
            str(table.num_rows),
            str(table.num_cols),
            str(getattr(table, 'prov', [{}])[0].get('page', 'N/A'))
        )
    
    console.print(table_display)
    
    # Show document structure (first 10 items)
    console.print(f"\n[bold]Document Structure (first 10 items):[/bold]")
    for i, item in enumerate(doc.iterate_items()):
        if i >= 10:
            break
        
        text = str(item.text)[:70]
        if len(str(item.text)) > 70:
            text += "..."
        
        console.print(f"  {i+1}. [{item.label}] {text}")
    
    # Look for "Fair Value" or "Contractual Principal" tables
    console.print(f"\n[bold]Searching for target tables...[/bold]")
    target_keywords = ["fair value", "contractual principal", "difference between"]
    
    found_tables = []
    for i, table in enumerate(tables):
        caption = getattr(table, 'caption', '').lower()
        if any(keyword in caption for keyword in target_keywords):
            found_tables.append((i, table))
    
    if found_tables:
        console.print(f"[green]✓ Found {len(found_tables)} relevant tables:[/green]")
        for idx, table in found_tables[:3]:
            console.print(f"  • Table {idx+1}: {getattr(table, 'caption', 'No caption')}")
    else:
        console.print(f"[yellow]⚠ No tables found with target keywords[/yellow]")
    
    console.print()
    return {
        'filename': pdf_path.name,
        'pages': len(doc.pages),
        'tables': len(tables),
        'texts': len(texts),
        'target_tables_found': len(found_tables)
    }


if __name__ == "__main__":
    console.print("\n[bold green]🔍 Docling Extraction Test[/bold green]\n")
    
    # Test files
    test_files = [
        Path("../raw_data/10k1224.pdf"),  # 2024 Annual Report (10-K)
        Path("../raw_data/10q0325.pdf"),  # Q1 2025 Report (10-Q)
    ]
    
    results = []
    for pdf_path in test_files:
        if not pdf_path.exists():
            console.print(f"[red]✗ File not found: {pdf_path}[/red]")
            continue
        
        try:
            result = test_extraction(pdf_path)
            results.append(result)
        except Exception as e:
            console.print(f"[red]✗ Error processing {pdf_path.name}: {e}[/red]")
    
    # Summary
    console.print("\n[bold]Summary:[/bold]")
    summary_table = RichTable(show_header=True, header_style="bold magenta")
    summary_table.add_column("File", style="cyan")
    summary_table.add_column("Pages", justify="right", style="yellow")
    summary_table.add_column("Tables", justify="right", style="green")
    summary_table.add_column("Texts", justify="right", style="blue")
    summary_table.add_column("Target Tables", justify="right", style="red")
    
    for r in results:
        summary_table.add_row(
            r['filename'],
            str(r['pages']),
            str(r['tables']),
            str(r['texts']),
            str(r['target_tables_found'])
        )
    
    console.print(summary_table)
    console.print()
