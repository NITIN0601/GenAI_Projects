#!/usr/bin/env python3
"""
Test Table Title Extraction - Captures ALL items including TOC page text.

Usage:
    python scripts/test_title_extraction.py           # All PDFs
    python scripts/test_title_extraction.py 10q0925   # Specific PDF

Output: data/table_name/<pdf_name>_titles.json
"""

import sys
import re
import json
from pathlib import Path
from datetime import datetime

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from docling.document_converter import DocumentConverter
from docling_core.types.doc import DocItemLabel


def get_page(item) -> int:
    if hasattr(item, 'prov') and item.prov:
        for p in item.prov:
            if hasattr(p, 'page_no'):
                return p.page_no
    return 1


def get_bbox_left(item) -> float:
    """Get left x-position from bounding box (for indentation detection)."""
    if hasattr(item, 'prov') and item.prov:
        for p in item.prov:
            if hasattr(p, 'bbox'):
                bbox = p.bbox
                # Try different bbox attribute names
                left = getattr(bbox, 'l', None) or getattr(bbox, 'left', None) or getattr(bbox, 'x', None)
                if left is not None:
                    return float(left)
    return 0.0


def classify_label(label) -> str:
    """Classify the Docling label type."""
    label_str = str(label).upper()
    if 'SECTION' in label_str:
        return 'SECTION_HEADER'
    if 'TITLE' in label_str:
        return 'TITLE'
    if 'CAPTION' in label_str:
        return 'CAPTION'
    if 'TEXT' in label_str:
        return 'TEXT'
    if 'LIST' in label_str:
        return 'LIST_ITEM'
    return label_str


def extract_all_items(pdf_path: Path, page_range: tuple = None) -> dict:
    """Extract ALL items including TEXT to understand TOC structure."""
    
    print(f"  📄 Loading {pdf_path.name}...")
    converter = DocumentConverter()
    result = converter.convert(str(pdf_path))
    doc = result.document
    
    items_list = list(doc.iterate_items())
    
    # Collect ALL items on TOC pages (pages 2-5) including TEXT
    toc_items = []
    all_sections = []
    tables = []
    
    for idx, item_data in enumerate(items_list):
        item = item_data[0] if isinstance(item_data, tuple) else item_data
        
        if not hasattr(item, 'text') or not item.text:
            continue
        
        text = str(item.text).strip()
        if len(text) < 3 or len(text) > 200:
            continue
        
        page = get_page(item)
        label = classify_label(item.label) if hasattr(item, 'label') else 'UNKNOWN'
        left_pos = get_bbox_left(item)
        
        item_info = {
            'page': page,
            'text': text,
            'label': label,
            'left_pos': round(left_pos, 1),  # For indentation detection
        }
        
        # Capture ALL items on TOC pages (pages 2-5)
        if page <= 5:
            toc_items.append(item_info)
        
        # Capture section headers throughout
        if label in ['SECTION_HEADER', 'TITLE', 'CAPTION']:
            all_sections.append(item_info)
        
        # Find tables
        if hasattr(item, 'label') and item.label == DocItemLabel.TABLE:
            if page_range and not (page_range[0] <= page <= page_range[1]):
                continue
            
            # Get preceding items for title detection
            preceding = []
            for back_idx in range(idx - 1, max(0, idx - 20), -1):
                prev = items_list[back_idx]
                prev_item = prev[0] if isinstance(prev, tuple) else prev
                if hasattr(prev_item, 'text') and prev_item.text:
                    prev_text = str(prev_item.text).strip()
                    prev_page = get_page(prev_item)
                    prev_label = classify_label(prev_item.label) if hasattr(prev_item, 'label') else 'UNKNOWN'
                    if 3 < len(prev_text) < 150 and prev_page >= page - 1:
                        preceding.append({
                            'text': prev_text,
                            'label': prev_label,
                            'page': prev_page,
                            'distance': idx - back_idx,
                        })
            
            tables.append({
                'page': page,
                'table_num': len(tables) + 1,
                'preceding_items': preceding[:10],
            })
    
    return {
        'pdf': pdf_path.name,
        'extracted_at': datetime.now().isoformat(),
        'toc_items': toc_items,  # ALL items on pages 2-5 for TOC analysis
        'all_sections': all_sections,
        'tables': tables,
        'total_tables': len(tables),
        'total_sections': len(all_sections),
    }


def process_pdf(pdf_path: Path, output_dir: Path, page_range: tuple = None):
    """Process single PDF."""
    result = extract_all_items(pdf_path, page_range)
    
    output_file = output_dir / f"{pdf_path.stem}_titles.json"
    with open(output_file, 'w') as f:
        json.dump(result, f, indent=2)
    
    # Show TOC page summary
    toc_count = len(result['toc_items'])
    print(f"  ✅ {pdf_path.name}: {result['total_tables']} tables, {result['total_sections']} sections")
    print(f"     TOC items (pages 2-5): {toc_count}")
    print(f"     → {output_file.name}")
    
    return result


def main():
    raw_dir = project_root / 'data' / 'raw'
    output_dir = project_root / 'data' / 'table_name'
    output_dir.mkdir(exist_ok=True)
    
    page_range = None
    
    if len(sys.argv) >= 2:
        pdf_name = sys.argv[1].replace('.pdf', '')
        pdfs = [raw_dir / f'{pdf_name}.pdf']
        if len(sys.argv) >= 3:
            parts = sys.argv[2].split('-')
            page_range = (int(parts[0]), int(parts[-1]))
    else:
        pdfs = list(raw_dir.glob('*.pdf'))
    
    print(f"\n{'='*60}")
    print(f"📊 Table Title & TOC Structure Extraction")
    print(f"   Now captures ALL items on TOC pages (pages 2-5)")
    print(f"{'='*60}\n")
    
    for pdf in sorted(pdfs):
        if pdf.exists():
            process_pdf(pdf, output_dir, page_range)
    
    print(f"\n✅ Done! Results in: {output_dir}/\n")


if __name__ == '__main__':
    main()
