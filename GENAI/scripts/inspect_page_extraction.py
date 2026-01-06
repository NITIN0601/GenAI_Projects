#!/usr/bin/env python3
"""
Page Extraction Inspector - Debug utility for table title extraction.

Usage:
    python scripts/inspect_page_extraction.py <pdf_name> <page>
    python scripts/inspect_page_extraction.py <pdf_name> <start_page>-<end_page>

Examples:
    python scripts/inspect_page_extraction.py 10q0925 33
    python scripts/inspect_page_extraction.py 10q0925 30-35
    python scripts/inspect_page_extraction.py 10k1224 45
"""

import sys
import re
import pandas as pd
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Patterns that indicate problematic extraction
ISSUE_PATTERNS = [
    (r'^at (january|february|march|april|may|june|july|august|september|october|november|december)\s+\d', 'DATE_HEADER'),
    (r'^(three|six|nine)\s+months?\s+ended', 'PERIOD_HEADER'),
    (r'notes to consolidated financial statements', 'SECTION_HEADER'),
    (r'^risk disclosures$', 'SECTION_HEADER'),
    (r'morgan stanley.*\(registrant\)', 'BOILERPLATE'),
    (r'^by (region|property type|product|industry)$', 'SUB_TABLE'),
]
COMPILED_ISSUES = [(re.compile(p, re.IGNORECASE), label) for p, label in ISSUE_PATTERNS]


def detect_issues(title: str) -> list:
    """Detect potential issues with a table title."""
    issues = []
    for pattern, label in COMPILED_ISSUES:
        if pattern.search(title.lower().strip()):
            issues.append(label)
    if len(title) < 5:
        issues.append('TOO_SHORT')
    return issues


def inspect_pages(pdf_name: str, start_page: int, end_page: int = None):
    """Show all extracted content from specified page(s)."""
    
    if end_page is None:
        end_page = start_page
    
    extracted_dir = project_root / 'data' / 'extracted_raw'
    xlsx_file = extracted_dir / f'{pdf_name}_tables.xlsx'
    
    if not xlsx_file.exists():
        print(f"❌ File not found: {xlsx_file}")
        print(f"Available: {[f.stem for f in extracted_dir.glob('*_tables.xlsx')]}")
        return
    
    xls = pd.read_excel(xlsx_file, sheet_name=None)
    toc = xls.get('TOC', xls.get('Index', pd.DataFrame()))
    
    if toc.empty:
        print("❌ No TOC/Index sheet found")
        return
    
    # Filter to requested page range
    page_tables = toc[(toc['Page'] >= start_page) & (toc['Page'] <= end_page)]
    
    if page_tables.empty:
        print(f"ℹ️  No tables found on page(s) {start_page}-{end_page}")
        return
    
    print(f"\n{'='*80}")
    print(f"📄 {pdf_name}.pdf | Pages {start_page}-{end_page} | Tables: {len(page_tables)}")
    print(f"{'='*80}")
    
    current_page = None
    for idx, row in page_tables.iterrows():
        page = row.get('Page', 'N/A')
        sheet_num = row.get('Sheet', 'N/A')
        table_title = str(row.get('Table Title', 'N/A'))
        issues = detect_issues(table_title)
        
        # Page header
        if page != current_page:
            current_page = page
            print(f"\n── Page {page} {'─'*65}")
        
        status = "⚠️" if issues else "✅"
        issue_str = f" [{', '.join(issues)}]" if issues else ""
        
        print(f"  {status} Sheet {sheet_num}: {table_title[:55]}{issue_str}")
        
        # Show metadata from the actual sheet
        sheet_data = xls.get(str(sheet_num), pd.DataFrame())
        if not sheet_data.empty:
            for i, srow in sheet_data.head(8).iterrows():
                first_col = str(srow.iloc[0]) if len(srow) > 0 else ''
                if first_col and first_col != 'nan' and ':' in first_col:
                    label = first_col.split(':')[0]
                    if label in ['Category (Parent)', 'Line Items', 'Column Header L1', 'Table Title']:
                        print(f"       {first_col[:70]}")
    
    print()


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return
    
    pdf_name = sys.argv[1].replace('.pdf', '')
    page_arg = sys.argv[2]
    
    # Parse page range (e.g., "30-35" or just "33")
    if '-' in page_arg:
        parts = page_arg.split('-')
        start_page, end_page = int(parts[0]), int(parts[1])
    else:
        start_page = int(page_arg)
        end_page = start_page
    
    inspect_pages(pdf_name, start_page, end_page)


if __name__ == '__main__':
    main()
