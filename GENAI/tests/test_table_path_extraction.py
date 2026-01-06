#!/usr/bin/env python3
"""
Test Script for Table Path Extraction - 10q0624.pdf

Standalone test script to validate table title path extraction.
Compares extracted output against expected values from tablepaths.md.

Usage:
    python tests/test_table_path_extraction.py
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import pandas as pd
from src.infrastructure.extraction.helpers.docling_helper import DoclingHelper, SectionHierarchyTracker
from docling_core.types.doc import DocItemLabel


# Expected table paths from tablepaths.md sample
EXPECTED_TABLES = [
    {"page": 8, "table_id": 1, "toc": "Management's Discussion and Analysis of Financial Condition and Results of Operations", 
     "main": "Management's Discussion and Analysis", "section1": "Executive Summary", "section2": "-", "section3": "-", "section4": "-",
     "table_title": "Selected Financial Information and Other Statistical Data"},
    {"page": 9, "table_id": 2, "toc": "Management's Discussion and Analysis of Financial Condition and Results of Operations",
     "main": "Management's Discussion and Analysis", "section1": "Executive Summary", "section2": "-", "section3": "-", "section4": "-",
     "table_title": "Reconciliations from U.S GAAP to Non-GAAP Consolidated Financial Measures"},
    {"page": 10, "table_id": 3, "toc": "Management's Discussion and Analysis of Financial Condition and Results of Operations",
     "main": "Management's Discussion and Analysis", "section1": "Executive Summary", "section2": "-", "section3": "-", "section4": "-",
     "table_title": "Non-GAAP Financial Measures by Business Segment"},
    {"page": 11, "table_id": 4, "toc": "Management's Discussion and Analysis of Financial Condition and Results of Operations",
     "main": "Management's Discussion and Analysis", "section1": "Business Segments", "section2": "Institutional Securities", "section3": "-", "section4": "-",
     "table_title": "Income Statement Information"},
    {"page": 11, "table_id": 5, "toc": "Management's Discussion and Analysis of Financial Condition and Results of Operations",
     "main": "Management's Discussion and Analysis", "section1": "Business Segments", "section2": "Institutional Securities", "section3": "Investment Banking", "section4": "-",
     "table_title": "Investment Banking Volumes"},
    {"page": 12, "table_id": 6, "toc": "Management's Discussion and Analysis of Financial Condition and Results of Operations",
     "main": "Management's Discussion and Analysis", "section1": "Business Segments", "section2": "Equity, Fixed Income and Other Net Revenues", "section3": "-", "section4": "-",
     "table_title": "Equity and Fixed Income Net Revenues"},
    {"page": 14, "table_id": 7, "toc": "Management's Discussion and Analysis of Financial Condition and Results of Operations",
     "main": "Management's Discussion and Analysis", "section1": "Business Segments", "section2": "Wealth Management", "section3": "-", "section4": "-",
     "table_title": "Income Statement Information"},
    {"page": 14, "table_id": 8, "toc": "Management's Discussion and Analysis of Financial Condition and Results of Operations",
     "main": "Management's Discussion and Analysis", "section1": "Business Segments", "section2": "Wealth Management", "section3": "-", "section4": "-",
     "table_title": "Wealth Management Metrics"},
    {"page": 14, "table_id": 9, "toc": "Management's Discussion and Analysis of Financial Condition and Results of Operations",
     "main": "Management's Discussion and Analysis", "section1": "Business Segments", "section2": "Wealth Management", "section3": "Net New Assets", "section4": "-",
     "table_title": "Advisor-led Channel"},
    {"page": 15, "table_id": 10, "toc": "Management's Discussion and Analysis of Financial Condition and Results of Operations",
     "main": "Management's Discussion and Analysis", "section1": "Business Segments", "section2": "Wealth Management", "section3": "Net New Assets", "section4": "-",
     "table_title": "Self-directed Channel"},
    {"page": 15, "table_id": 11, "toc": "Management's Discussion and Analysis of Financial Condition and Results of Operations",
     "main": "Management's Discussion and Analysis", "section1": "Business Segments", "section2": "Wealth Management", "section3": "Net New Assets", "section4": "-",
     "table_title": "Workplace Channel"},
    {"page": 16, "table_id": 12, "toc": "Management's Discussion and Analysis of Financial Condition and Results of Operations",
     "main": "Management's Discussion and Analysis", "section1": "Business Segments", "section2": "Wealth Management", "section3": "Non-interest Expense", "section4": "-",
     "table_title": "Fee-Based Client Assets Rollforwards"},
    {"page": 16, "table_id": 13, "toc": "Management's Discussion and Analysis of Financial Condition and Results of Operations",
     "main": "Management's Discussion and Analysis", "section1": "Business Segments", "section2": "Wealth Management", "section3": "Non-interest Expense", "section4": "-",
     "table_title": "Average Fee Rates"},
    {"page": 17, "table_id": 14, "toc": "Management's Discussion and Analysis of Financial Condition and Results of Operations",
     "main": "Management's Discussion and Analysis", "section1": "Business Segments", "section2": "Investment Management", "section3": "-", "section4": "-",
     "table_title": "Income Statement Information"},
    {"page": 18, "table_id": 15, "toc": "Management's Discussion and Analysis of Financial Condition and Results of Operations",
     "main": "Management's Discussion and Analysis", "section1": "Business Segments", "section2": "Investment Management", "section3": "Non-interest Expense", "section4": "-",
     "table_title": "Assets under Management or Supervision Rollforwards"},
    {"page": 18, "table_id": 16, "toc": "Management's Discussion and Analysis of Financial Condition and Results of Operations",
     "main": "Management's Discussion and Analysis", "section1": "Business Segments", "section2": "Investment Management", "section3": "Non-interest Expense", "section4": "-",
     "table_title": "Average AUM"},
    {"page": 18, "table_id": 17, "toc": "Management's Discussion and Analysis of Financial Condition and Results of Operations",
     "main": "Management's Discussion and Analysis", "section1": "Business Segments", "section2": "Investment Management", "section3": "Non-interest Expense", "section4": "-",
     "table_title": "Average Fee Rates"},
]


def normalize(text: str) -> str:
    """Normalize text for comparison (lowercase, strip, collapse spaces)."""
    if not text or text == '-':
        return '-'
    import re
    return re.sub(r'\s+', ' ', text.lower().strip())


def compare_fields(expected: dict, actual: dict) -> dict:
    """Compare expected vs actual fields, return mismatches."""
    mismatches = {}
    fields = ['toc', 'main', 'section1', 'section2', 'section3', 'section4', 'table_title']
    
    for field in fields:
        exp_val = normalize(expected.get(field, '-'))
        act_val = normalize(actual.get(field, '-'))
        
        # Flexible matching - allow partial matches for long strings
        if exp_val != act_val:
            if not (exp_val in act_val or act_val in exp_val):
                mismatches[field] = {'expected': expected.get(field, '-'), 'actual': actual.get(field, '-')}
    
    return mismatches


def extract_all_tables_with_context(pdf_path: str) -> list:
    """
    Extract all tables from PDF with their complete hierarchical context.
    
    Returns list of dicts with: page, table_index, toc, main, section1-4, table_title
    """
    print(f"\n📄 Converting PDF: {pdf_path}")
    doc_result = DoclingHelper.convert_pdf(pdf_path)
    doc = doc_result.document
    
    # Extract TOC sections
    print("📑 Extracting TOC sections...")
    toc_sections = DoclingHelper.extract_toc_sections(doc)
    print(f"   Found {len(toc_sections)} TOC entries")
    
    # Initialize section hierarchy tracker
    tracker = SectionHierarchyTracker()
    
    # Get all items and pre-scan for section headers
    items_list = list(doc.iterate_items())
    
    # Collect all section headers for pre-scan
    all_headers = []
    for item_data in items_list:
        item = item_data[0] if isinstance(item_data, tuple) else item_data
        
        if not hasattr(item, 'label') or not item.label:
            continue
        
        label_str = str(item.label).upper()
        if 'SECTION' not in label_str and 'TITLE' not in label_str:
            continue
        
        if not hasattr(item, 'text') or not item.text:
            continue
        
        text = str(item.text).strip()
        if len(text) < 5 or len(text) > 100:
            continue
        
        page = DoclingHelper.get_item_page(item)
        all_headers.append((page, text))
    
    # Pre-scan headers
    tracker.pre_scan_headers(all_headers)
    print(f"   Pre-scanned {len(all_headers)} section headers")
    
    # Extract tables with context
    tables = []
    table_index = 0
    current_hierarchy = tracker.get_current_hierarchy()
    
    for item_data in items_list:
        item = item_data[0] if isinstance(item_data, tuple) else item_data
        
        page = DoclingHelper.get_item_page(item)
        
        # Update hierarchy when we see a section header
        if hasattr(item, 'label') and item.label:
            label_str = str(item.label).upper()
            if 'SECTION' in label_str or 'TITLE' in label_str:
                if hasattr(item, 'text') and item.text:
                    text = str(item.text).strip()
                    if 5 < len(text) < 100:
                        current_hierarchy = tracker.process_header(text, page)
        
        # Process tables
        if hasattr(item, 'label') and item.label == DocItemLabel.TABLE:
            # Use hybrid method for better table title extraction
            table_title = DoclingHelper.extract_table_title_hybrid(doc, item, table_index, page)
            
            tables.append({
                'page': page,
                'table_index': table_index,
                'toc': current_hierarchy.get('toc', '-') or '-',
                'main': current_hierarchy.get('main', '-') or '-',
                'section1': current_hierarchy.get('section1', '-') or '-',
                'section2': current_hierarchy.get('section2', '-') or '-',
                'section3': current_hierarchy.get('section3', '-') or '-',
                'section4': current_hierarchy.get('section4', '-') or '-',
                'table_title': table_title or '-'
            })
            table_index += 1
    
    # Cleanup
    DoclingHelper.clear_toc_cache()
    
    return tables


def run_test():
    """Run the table path extraction test."""
    pdf_path = str(project_root / 'data' / 'raw' / '10q0624.pdf')
    
    print("=" * 80)
    print("🧪 TABLE PATH EXTRACTION TEST - 10q0624.pdf")
    print("=" * 80)
    
    # Extract tables
    extracted = extract_all_tables_with_context(pdf_path)
    print(f"\n📊 Extracted {len(extracted)} tables total")
    
    # Filter to pages 8-18 for comparison
    extracted_filtered = [t for t in extracted if 8 <= t['page'] <= 18]
    print(f"   Found {len(extracted_filtered)} tables on pages 8-18")
    
    # Show extracted tables
    print("\n" + "=" * 80)
    print("📋 EXTRACTED TABLES (Pages 8-18)")
    print("=" * 80)
    
    for t in extracted_filtered:
        print(f"\nPage {t['page']}, Table {t['table_index'] + 1}:")
        print(f"  TOC:      {t['toc'][:60]}..." if len(t['toc']) > 60 else f"  TOC:      {t['toc']}")
        print(f"  Main:     {t['main'][:50]}..." if len(t['main']) > 50 else f"  Main:     {t['main']}")
        print(f"  Section1: {t['section1']}")
        print(f"  Section2: {t['section2']}")
        print(f"  Section3: {t['section3']}")
        print(f"  Section4: {t['section4']}")
        print(f"  Title:    {t['table_title']}")
    
    # Compare with expected
    print("\n" + "=" * 80)
    print("🔍 COMPARISON WITH EXPECTED (from tablepaths.md)")
    print("=" * 80)
    
    passed = 0
    failed = 0
    
    for expected in EXPECTED_TABLES:
        page = expected['page']
        
        # Find matching extracted table by page and table title
        matches = [t for t in extracted_filtered if t['page'] == page]
        
        if not matches:
            print(f"\n❌ FAIL: No table found on page {page}")
            print(f"   Expected: {expected['table_title']}")
            failed += 1
            continue
        
        # Try to find best match by title
        best_match = None
        for m in matches:
            if normalize(expected['table_title']) in normalize(m['table_title']) or \
               normalize(m['table_title']) in normalize(expected['table_title']):
                best_match = m
                break
        
        if not best_match:
            best_match = matches[0]  # Default to first match on page
        
        mismatches = compare_fields(expected, best_match)
        
        if not mismatches:
            print(f"\n✅ PASS: Page {page} - {expected['table_title'][:40]}...")
            passed += 1
        else:
            print(f"\n❌ FAIL: Page {page} - {expected['table_title'][:40]}...")
            for field, vals in mismatches.items():
                print(f"   {field}:")
                print(f"     Expected: {vals['expected']}")
                print(f"     Actual:   {vals['actual']}")
            failed += 1
    
    # Summary
    print("\n" + "=" * 80)
    print("📊 TEST SUMMARY")
    print("=" * 80)
    print(f"  ✅ Passed: {passed}/{len(EXPECTED_TABLES)}")
    print(f"  ❌ Failed: {failed}/{len(EXPECTED_TABLES)}")
    print(f"  Success Rate: {100 * passed / len(EXPECTED_TABLES):.1f}%")
    
    return passed == len(EXPECTED_TABLES)


if __name__ == '__main__':
    success = run_test()
    sys.exit(0 if success else 1)
