#!/usr/bin/env python3
"""
Extract document structure with headings, subheadings, and table context.
This is the KEY to proper table organization!
"""

import sys
sys.path.insert(0, '.')

from pathlib import Path
from rich.console import Console
from rich.tree import Tree
from docling.document_converter import DocumentConverter
from docling_core.types.doc import DocItemLabel
import json

console = Console()


def extract_document_structure(pdf_path):
    """
    Extract full document structure including:
    - Main headings (H1, H2, H3)
    - Subheadings
    - Table positions within sections
    - Table context (what section/heading it belongs to)
    """
    filename = Path(pdf_path).name
    console.print(f"\n[bold cyan]Extracting structure from {filename}...[/bold cyan]")
    
    converter = DocumentConverter()
    result = converter.convert(pdf_path)
    
    # Build document structure
    structure = {
        'filename': filename,
        'sections': [],
        'tables_with_context': []
    }
    
    current_section = None
    current_subsection = None
    section_stack = []
    
    # Iterate through document items in order
    for item in result.document.iterate_items():
        item_label = item.label
        
        # Track headings
        if item_label == DocItemLabel.SECTION_HEADER:
            # Determine heading level from text or position
            text = item.text if hasattr(item, 'text') else str(item)
            level = get_heading_level(text, item)
            
            section_info = {
                'level': level,
                'text': text,
                'page': getattr(item, 'prov', [{}])[0].get('page_no', 0) if hasattr(item, 'prov') else 0,
                'subsections': [],
                'tables': []
            }
            
            if level == 1:
                structure['sections'].append(section_info)
                current_section = section_info
                current_subsection = None
                section_stack = [section_info]
            elif level == 2 and current_section:
                current_section['subsections'].append(section_info)
                current_subsection = section_info
                section_stack = [current_section, section_info]
            elif level == 3 and current_subsection:
                current_subsection['subsections'].append(section_info)
                section_stack = [current_section, current_subsection, section_info]
        
        # Track tables with their context
        elif item_label == DocItemLabel.TABLE:
            table_info = {
                'table_index': len(structure['tables_with_context']),
                'text': item.export_to_markdown() if hasattr(item, 'export_to_markdown') else str(item.text),
                'page': getattr(item, 'prov', [{}])[0].get('page_no', 0) if hasattr(item, 'prov') else 0,
                'context': {
                    'section': section_stack[0]['text'] if len(section_stack) > 0 else None,
                    'subsection': section_stack[1]['text'] if len(section_stack) > 1 else None,
                    'subsubsection': section_stack[2]['text'] if len(section_stack) > 2 else None,
                    'heading_path': ' > '.join([s['text'] for s in section_stack])
                }
            }
            
            structure['tables_with_context'].append(table_info)
            
            # Add to current section
            if section_stack:
                section_stack[-1]['tables'].append(table_info['table_index'])
    
    return structure


def get_heading_level(text, item):
    """Determine heading level from text or formatting."""
    # Simple heuristic - can be improved
    text_upper = text.upper()
    
    # Level 1: All caps, short
    if text == text_upper and len(text) < 100:
        return 1
    
    # Level 2: Title case, medium
    if text.istitle() and len(text) < 150:
        return 2
    
    # Default to level 3
    return 3


def display_structure(structure):
    """Display document structure as a tree."""
    tree = Tree(f"[bold]{structure['filename']}[/bold]")
    
    for section in structure['sections']:
        section_node = tree.add(f"[cyan]{section['text']}[/cyan] (Page {section['page']})")
        
        if section['tables']:
            section_node.add(f"[yellow]📊 {len(section['tables'])} table(s)[/yellow]")
        
        for subsection in section.get('subsections', []):
            subsection_node = section_node.add(f"[green]{subsection['text']}[/green]")
            
            if subsection['tables']:
                subsection_node.add(f"[yellow]📊 {len(subsection['tables'])} table(s)[/yellow]")
    
    console.print(tree)


def create_enhanced_metadata(table_info):
    """
    Create enhanced metadata for vector DB storage.
    This is the KEY improvement!
    """
    return {
        # Document info
        'filename': table_info.get('filename'),
        'page_number': table_info.get('page'),
        
        # Hierarchical context (NEW!)
        'section_heading': table_info['context']['section'],
        'subsection_heading': table_info['context']['subsection'],
        'subsubsection_heading': table_info['context']['subsubsection'],
        'heading_path': table_info['context']['heading_path'],
        
        # Table info
        'table_index': table_info['table_index'],
        
        # Searchable fields
        'section_keywords': extract_keywords(table_info['context']['section']),
        'full_context': f"{table_info['context']['heading_path']} | Table on page {table_info['page']}"
    }


def extract_keywords(text):
    """Extract keywords from heading text."""
    if not text:
        return []
    
    # Simple keyword extraction
    words = text.lower().split()
    # Remove common words
    stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for'}
    keywords = [w for w in words if w not in stop_words and len(w) > 3]
    return keywords


def search_by_heading(structure, heading_query):
    """Search tables by heading/section."""
    results = []
    query_lower = heading_query.lower()
    
    for table in structure['tables_with_context']:
        heading_path = table['context']['heading_path'].lower()
        
        if query_lower in heading_path:
            results.append(table)
    
    return results


if __name__ == "__main__":
    console.print("\n[bold]Extracting Document Structure with Headings[/bold]")
    console.print("=" * 70)
    
    # Test on one PDF
    pdf_path = "../raw_data/10k1224.pdf"
    
    if Path(pdf_path).exists():
        structure = extract_document_structure(pdf_path)
        
        # Display structure
        console.print(f"\n[bold green]Document Structure:[/bold green]")
        display_structure(structure)
        
        # Show tables with context
        console.print(f"\n[bold]Tables with Context:[/bold]")
        for i, table in enumerate(structure['tables_with_context'][:5], 1):
            console.print(f"\n[cyan]Table {i}:[/cyan]")
            console.print(f"  Page: {table['page']}")
            console.print(f"  Section: {table['context']['section']}")
            console.print(f"  Subsection: {table['context']['subsection']}")
            console.print(f"  Full path: {table['context']['heading_path']}")
            console.print(f"  Preview: {table['text'][:200]}...")
        
        # Save structure
        with open('document_structure.json', 'w') as f:
            json.dump(structure, f, indent=2, default=str)
        
        console.print(f"\n[green]✓ Structure saved to document_structure.json[/green]")
        
        # Example search
        console.print(f"\n[bold]Example: Search for 'Fair Value' tables:[/bold]")
        fair_value_tables = search_by_heading(structure, 'fair value')
        console.print(f"Found {len(fair_value_tables)} tables in Fair Value sections")
        
        for table in fair_value_tables[:3]:
            console.print(f"  • {table['context']['heading_path']}")
