#!/usr/bin/env python3
"""
Example: Multi-year table consolidation using enhanced metadata.

Demonstrates how to:
1. Query tables across multiple years
2. Consolidate into single table with year columns
3. Use enhanced metadata for precise filtering
"""

import sys
sys.path.insert(0, '/Users/nitin/Desktop/Chatbot/Morgan/GENAI')

from embeddings.unified_vectordb import get_unified_vectordb
from src.models.vectordb_schemas import TableChunk, EnhancedTableMetadata
from typing import List, Dict
import pandas as pd


def consolidate_tables_by_period(results: List[Dict]) -> pd.DataFrame:
    """
    Consolidate tables from multiple periods into single table.
    
    Args:
        results: Search results from VectorDB
        
    Returns:
        DataFrame with rows as line items, columns as periods
    """
    # Group by table title and line item
    tables_by_period = {}
    
    for result in results:
        metadata = result['metadata']
        period = metadata.get('fiscal_period_end', f"{metadata['year']}-Q{metadata.get('quarter', '4')}")
        
        # Parse table content
        content = result['content']
        
        # Store by period
        if period not in tables_by_period:
            tables_by_period[period] = {}
        
        # Extract line items and values
        for line in content.split('\n'):
            if '|' in line:
                parts = [p.strip() for p in line.split('|')]
                if len(parts) >= 2:
                    line_item = parts[0]
                    value = parts[1] if len(parts) > 1 else ''
                    tables_by_period[period][line_item] = value
    
    # Convert to DataFrame
    df = pd.DataFrame(tables_by_period)
    df = df.sort_index()
    
    return df


def example_multi_year_query():
    """Example: Query total assets across multiple years."""
    print("=" * 80)
    print("MULTI-YEAR TABLE CONSOLIDATION EXAMPLE")
    print("=" * 80)
    
    # Initialize VectorDB
    vs = get_unified_vectordb("chromadb")
    
    # Query: "Show me total assets for 2023-2025"
    print("\nQuery: 'Show me total assets for 2023-2025'")
    print()
    
    # Search with enhanced filters
    from embeddings.providers import get_embedding_manager
    em = get_embedding_manager()
    
    query_embedding = em.generate_embedding("total assets")
    
    results = vs.search(
        query_embedding=query_embedding,
        top_k=20,
        filters={
            "statement_type": "balance_sheet",
            "company_ticker": "AAPL"
        }
    )
    
    print(f"Found {len(results)} results")
    print()
    
    # Filter by fiscal periods
    periods_of_interest = ["2023-12-31", "2024-12-31", "2025-06-30"]
    filtered_results = [
        r for r in results
        if r['metadata'].get('fiscal_period_end') in periods_of_interest
    ]
    
    print(f"Filtered to {len(filtered_results)} results for periods: {periods_of_interest}")
    print()
    
    # Consolidate
    if filtered_results:
        consolidated = consolidate_tables_by_period(filtered_results)
        
        print("Consolidated Table:")
        print(consolidated)
        print()
        
        # Show specific row
        if 'Total Assets' in consolidated.index:
            print("Total Assets across periods:")
            print(consolidated.loc['Total Assets'])


def example_precise_filtering():
    """Example: Precise filtering using enhanced metadata."""
    print("\n" + "=" * 80)
    print("PRECISE FILTERING EXAMPLE")
    print("=" * 80)
    
    vs = get_unified_vectordb("chromadb")
    em = get_embedding_manager()
    
    # Query: "What were Q2 2025 revenues in millions?"
    print("\nQuery: 'What were Q2 2025 revenues in millions?'")
    print()
    
    query_embedding = em.generate_embedding("revenue")
    
    results = vs.search(
        query_embedding=query_embedding,
        top_k=5,
        filters={
            "statement_type": "income_statement",
            "fiscal_period_end": "2025-06-30",
            "units": "millions",  # Critical!
            "currency": "USD"
        }
    )
    
    print(f"Found {len(results)} results with precise filters:")
    print("  - Statement type: income_statement")
    print("  - Period: 2025-06-30")
    print("  - Units: millions")
    print("  - Currency: USD")
    print()
    
    for i, result in enumerate(results, 1):
        print(f"{i}. {result['metadata']['table_title']}")
        print(f"   Content preview: {result['content'][:100]}...")
        print()


def example_related_tables():
    """Example: Finding related tables."""
    print("\n" + "=" * 80)
    print("RELATED TABLES EXAMPLE")
    print("=" * 80)
    
    vs = get_unified_vectordb("chromadb")
    em = get_embedding_manager()
    
    # Find balance sheet
    print("\nFinding balance sheet...")
    
    query_embedding = em.generate_embedding("balance sheet")
    
    results = vs.search(
        query_embedding=query_embedding,
        top_k=1,
        filters={
            "statement_type": "balance_sheet",
            "fiscal_period_end": "2025-06-30"
        }
    )
    
    if results:
        balance_sheet = results[0]
        print(f"Found: {balance_sheet['metadata']['table_title']}")
        
        # Get related tables
        related_ids = balance_sheet['metadata'].get('related_tables', [])
        
        if related_ids:
            print(f"\nRelated tables: {len(related_ids)}")
            
            # Fetch related tables
            for related_id in related_ids:
                related_results = vs.get_by_metadata(
                    filters={"chunk_reference_id": related_id},
                    limit=1
                )
                
                if related_results:
                    print(f"  - {related_results[0]['metadata']['table_title']}")
        else:
            print("\nNo related tables found (metadata not populated yet)")


def main():
    """Run all examples."""
    print("\n")
    print("╔" + "=" * 78 + "╗")
    print("║" + " " * 15 + "ENHANCED METADATA EXAMPLES" + " " * 37 + "║")
    print("╚" + "=" * 78 + "╝")
    
    try:
        example_multi_year_query()
        example_precise_filtering()
        example_related_tables()
    except Exception as e:
        print(f"\n⚠️  Note: Examples require populated VectorDB")
        print(f"   Error: {e}")
        print("\n   Run process_raw_data.py first to populate data")
    
    print("\n" + "=" * 80)
    print("EXAMPLES COMPLETE")
    print("=" * 80)
    print("\nKey Features Demonstrated:")
    print("1. Multi-year table consolidation")
    print("2. Precise filtering (statement type, units, currency)")
    print("3. Related table traversal")
    print("\n" + "=" * 80)


if __name__ == '__main__':
    main()
