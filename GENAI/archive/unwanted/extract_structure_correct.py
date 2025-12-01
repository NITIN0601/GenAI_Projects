#!/usr/bin/env python3
"""
CORRECT heading extraction using Docling's document structure.
Handles multi-page tables automatically.
"""

import sys
sys.path.insert(0, '.')

from pathlib import Path
from rich.console import Console
from rich.tree import Tree
from docling.document_converter import DocumentConverter
from docling_core.types.doc import DocItemLabel, TableItem
import json

console = Console()


def extract_document_structure_correct(pdf_path):
    """
    Extract document structure using Docling's ACTUAL hierarchy.
    This is the CORRECT way!
    """
    filename = Path(pdf_path).name
    console.print(f"\n[bold cyan]Extracting structure from {filename}...[/bold cyan]")
    
    converter = DocumentConverter()
    result = converter.convert(pdf_path)
    
    # Docling provides document structure through its hierarchy
    structure = {
        'filename': filename,
        'sections': [],
        'tables_with_context': []
    }
    
    # Track current context as we iterate
    current_headings = {
        1: None,  # H1
        2: None,  # H2
        3: None,  # H3
        4: None,  # H4
    }
    
    # Iterate through document items
    for item in result.document.iterate_items():
        
        # Handle section headers
        if item.label == DocItemLabel.SECTION_HEADER:
            # Docling provides the heading level!
            level = item.self_ref.split('.').count('.')  # Count dots in reference
            if level == 0:
                level = 1
            
            heading_text = item.text if hasattr(item, 'text') else str(item)
            
            # Update current headings
            current_headings[level] = heading_text
            # Clear lower levels
            for l in range(level + 1, 5):
                current_headings[l] = None
            
            console.print(f"  [cyan]H{level}:[/cyan] {heading_text}")
        
        # Handle tables
        elif item.label == DocItemLabel.TABLE:
            # Get table info
            table_data = extract_table_info(item)
            
            # Build heading path
            heading_path_parts = [h for h in [
                current_headings.get(1),
                current_headings.get(2),
                current_headings.get(3),
                current_headings.get(4)
            ] if h]
            
            table_info = {
                'table_index': len(structure['tables_with_context']),
                'text': table_data['text'],
                'page_start': table_data['page_start'],
                'page_end': table_data['page_end'],
                'is_multi_page': table_data['is_multi_page'],
                'context': {
                    'section_heading': current_headings.get(1),
                    'subsection_heading': current_headings.get(2),
                    'subsubsection_heading': current_headings.get(3),
                    'heading_path': ' > '.join(heading_path_parts),
                    'table_caption': table_data.get('caption', '')
                }
            }
            
            structure['tables_with_context'].append(table_info)
            
            # Show table info
            console.print(f"  [yellow]Table {table_info['table_index']}:[/yellow]")
            console.print(f"    Path: {table_info['context']['heading_path']}")
            console.print(f"    Pages: {table_data['page_start']}-{table_data['page_end']}")
            if table_data['is_multi_page']:
                console.print(f"    [green]✓ Multi-page table detected[/green]")
    
    return structure


def extract_table_info(table_item: TableItem):
    """
    Extract table information including multi-page detection.
    Docling automatically handles multi-page tables!
    """
    # Get table text
    table_text = table_item.export_to_markdown() if hasattr(table_item, 'export_to_markdown') else str(table_item.text)
    
    # Get page information
    # Docling tracks which pages a table spans
    prov = table_item.prov if hasattr(table_item, 'prov') else []
    
    pages = set()
    for p in prov:
        if hasattr(p, 'page_no'):
            pages.add(p.page_no)
    
    page_start = min(pages) if pages else 0
    page_end = max(pages) if pages else 0
    is_multi_page = len(pages) > 1
    
    # Get caption if available
    caption = table_item.caption if hasattr(table_item, 'caption') else None
    
    return {
        'text': table_text,
        'page_start': page_start,
        'page_end': page_end,
        'is_multi_page': is_multi_page,
        'pages_spanned': len(pages),
        'caption': caption
    }


def search_by_heading_path(structure, query):
    """
    Search tables by heading path.
    Example: "Fair Value Option" will find all tables under that heading.
    """
    results = []
    query_lower = query.lower()
    
    for table in structure['tables_with_context']:
        heading_path = table['context']['heading_path'].lower()
        section = (table['context']['section_heading'] or '').lower()
        subsection = (table['context']['subsection_heading'] or '').lower()
        
        # Check if query matches any part of the path
        if (query_lower in heading_path or 
            query_lower in section or 
            query_lower in subsection):
            results.append(table)
    
    return results


if __name__ == "__main__":
    console.print("\n[bold]Correct Document Structure Extraction[/bold]")
    console.print("=" * 70)
    
    # Test on one PDF
    pdf_path = "../raw_data/10q0320.pdf"
    
    if Path(pdf_path).exists():
        structure = extract_document_structure_correct(pdf_path)
        
        # Summary
        console.print(f"\n[bold green]Summary:[/bold green]")
        console.print(f"  Total tables: {len(structure['tables_with_context'])}")
        
        multi_page_tables = [t for t in structure['tables_with_context'] if t['is_multi_page']]
        console.print(f"  Multi-page tables: {len(multi_page_tables)}")
        
        # Show multi-page tables
        if multi_page_tables:
            console.print(f"\n[bold]Multi-Page Tables:[/bold]")
            for table in multi_page_tables:
                console.print(f"  Table {table['table_index']}: Pages {table['page_start']}-{table['page_end']}")
                console.print(f"    Path: {table['context']['heading_path']}")
        
        # Example search
        console.print(f"\n[bold]Example: Search for 'Fair Value' tables:[/bold]")
        fair_value_tables = search_by_heading_path(structure, 'fair value')
        console.print(f"Found {len(fair_value_tables)} tables")
        
        for table in fair_value_tables[:5]:
            console.print(f"  • {table['context']['heading_path']}")
            if table['context']['table_caption']:
                console.print(f"    Caption: {table['context']['table_caption']}")
        
        # Save
        with open('correct_document_structure.json', 'w') as f:
            json.dump(structure, f, indent=2, default=str)
        
        console.print(f"\n[green]✓ Structure saved to correct_document_structure.json[/green]")
