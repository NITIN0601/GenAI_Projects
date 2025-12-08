#!/usr/bin/env python3
"""
Test extraction on real PDF tables and show input/output examples.
"""

from pathlib import Path
from docling.document_converter import DocumentConverter
from docling_core.types.doc import DocItemLabel
from embeddings.table_chunker import TableChunker
from src.domain.tables import TableMetadata
from datetime import datetime
from rich.console import Console
from rich.panel import Panel

console = Console()

def extract_sample_tables(pdf_path: str, max_tables: int = 4):
    """Extract sample tables from PDF and show before/after formatting."""
    
    # Convert to Path object
    pdf_path = Path(pdf_path).resolve()
    
    console.print(Panel.fit(
        f"[bold cyan]Extracting Sample Tables from {pdf_path.name}[/bold cyan]",
        border_style="cyan"
    ))
    
    # Convert PDF
    console.print("\n[yellow]Converting PDF with Docling...[/yellow]")
    converter = DocumentConverter()
    result = converter.convert(str(pdf_path))
    doc = result.document
    
    # Find tables - iterate_items returns tuples of (item, level)
    tables = []
    for item_data in doc.iterate_items():
        # Handle both tuple and direct item formats
        if isinstance(item_data, tuple):
            item = item_data[0]
        else:
            item = item_data
        
        if hasattr(item, 'label') and item.label == DocItemLabel.TABLE:
            tables.append(item)
    
    console.print(f"[green]✓ Found {len(tables)} tables total[/green]\n")
    
    # Process first N tables
    chunker = TableChunker(flatten_headers=False)  # Use spanning header format
    
    for i, table_item in enumerate(tables[:max_tables], 1):
        console.print(f"\n{'='*80}")
        console.print(f"[bold]TABLE {i}[/bold]")
        console.print(f"{'='*80}\n")
        
        # Get table info
        caption = table_item.caption if hasattr(table_item, 'caption') else f"Table {i}"
        page_no = 1
        if hasattr(table_item, 'prov') and table_item.prov:
            for p in table_item.prov:
                if hasattr(p, 'page_no'):
                    page_no = p.page_no
                    break
        
        console.print(f"[cyan]Caption:[/cyan] {caption}")
        console.print(f"[cyan]Page:[/cyan] {page_no}\n")
        
        # Get table text
        table_text = table_item.export_to_markdown() if hasattr(table_item, 'export_to_markdown') else str(table_item.text)
        
        # Show INPUT
        console.print("[bold yellow]INPUT (Original from Docling):[/bold yellow]")
        console.print(Panel(table_text[:500] + ("..." if len(table_text) > 500 else ""), 
                           border_style="yellow", 
                           title="Original Table"))
        
        # Process with chunker
        metadata = TableMetadata(
            source_doc=pdf_path.name,
            page_no=page_no,
            table_title=caption,
            year=2022,
            quarter=None,
            report_type="10-K",
            extraction_date=datetime.now()
        )
        
        chunks = chunker.chunk_table(table_text, metadata)
        
        # Show OUTPUT
        console.print("\n[bold green]OUTPUT (After Formatting):[/bold green]")
        for j, chunk in enumerate(chunks, 1):
            if len(chunks) > 1:
                console.print(f"\n[magenta]Chunk {j}/{len(chunks)}:[/magenta]")
            
            output_text = chunk.content[:500] + ("..." if len(chunk.content) > 500 else "")
            console.print(Panel(output_text, 
                               border_style="green", 
                               title=f"Formatted Table (Chunk {j})"))
        
        # Show analysis
        lines_input = table_text.split('\n')
        lines_output = chunks[0].content.split('\n')
        
        console.print(f"\n[bold]Analysis:[/bold]")
        console.print(f"  Input lines: {len(lines_input)}")
        console.print(f"  Output lines: {len(lines_output)}")
        console.print(f"  Chunks created: {len(chunks)}")
        
        # Check for spanning headers
        header_lines_input = [l for l in lines_input[:5] if l.strip() and '---' not in l]
        header_lines_output = [l for l in lines_output[:5] if l.strip() and '---' not in l]
        
        if len(header_lines_input) > len(header_lines_output):
            console.print(f"  [green]✓ Headers flattened: {len(header_lines_input)} → {len(header_lines_output)} rows[/green]")
        else:
            console.print(f"  [blue]ℹ Headers preserved as-is[/blue]")
    
    console.print(f"\n{'='*80}\n")
    console.print("[bold green]✓ Sample extraction complete![/bold green]\n")


if __name__ == "__main__":
    import sys
    
    pdf_path = sys.argv[1] if len(sys.argv) > 1 else "../raw_data/10k1222.pdf"
    max_tables = int(sys.argv[2]) if len(sys.argv) > 2 else 4
    
    extract_sample_tables(pdf_path, max_tables)
