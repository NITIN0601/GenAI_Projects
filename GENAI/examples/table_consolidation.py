#!/usr/bin/env python3
"""
Example: Multi-year table consolidation and transpose for RAG.

Demonstrates the complete workflow:
1. Query VectorDB for same table across multiple years
2. Consolidate into single table
3. Transpose for readability
4. Validate data integrity
"""

import sys
sys.path.insert(0, '/Users/nitin/Desktop/Chatbot/Morgan/GENAI')

from embeddings.unified_vectordb import get_unified_vectordb
from embeddings.providers import get_embedding_manager
from rag.table_consolidator import get_table_consolidator, consolidate_and_transpose


def example_consolidate_balance_sheet():
    """
    Example: Consolidate balance sheet across 2020-2024.
    
    Input:
        - 5 separate tables (one per year)
        - Same structure (consistent row headers)
    
    Output:
        - 1 consolidated transposed table
        - Years as rows, line items as columns
        - Zero data loss
    """
    print("=" * 80)
    print("MULTI-YEAR TABLE CONSOLIDATION & TRANSPOSE")
    print("=" * 80)
    
    # Initialize
    vs = get_unified_vectordb("chromadb")
    em = get_embedding_manager()
    consolidator = get_table_consolidator()
    
    # Step 1: Query for "Consolidated Balance Sheet" across years
    print("\nStep 1: Querying VectorDB for 'Consolidated Balance Sheet' (2020-2024)...")
    
    query_embedding = em.generate_embedding("Consolidated Balance Sheet")
    
    search_results = vs.search(
        query_embedding=query_embedding,
        top_k=50,  # Get more results to cover all years
        filters={
            "statement_type": "balance_sheet",
            "table_title": "Consolidated Balance Sheet"
        }
    )
    
    print(f"   Found {len(search_results)} results")
    
    # Step 2: Consolidate tables
    print("\nStep 2: Consolidating tables from multiple years...")
    
    result = consolidator.consolidate_multi_year_tables(
        search_results=search_results,
        table_title="Consolidated Balance Sheet"
    )
    
    if 'error' in result:
        print(f"   Error: {result['error']}")
        return
    
    print(f"   Years found: {result['years']}")
    print(f"   Row headers: {len(result['original_format']['row_headers'])}")
    
    # Step 3: Display original format (horizontal, wide)
    print("\n" + "=" * 80)
    print("ORIGINAL FORMAT (Horizontal - Wide)")
    print("=" * 80)
    
    original = result['original_format']
    print(f"\nRow Headers: {', '.join(original['row_headers'][:5])}...")
    print(f"Years: {original['years']}")
    
    # Show sample data
    print("\nSample Data (first 3 rows):")
    for i, row_header in enumerate(original['row_headers'][:3]):
        print(f"\n{row_header}:")
        for year in original['years']:
            value = original['data'][row_header].get(str(year), 'N/A')
            print(f"  {year}: {value}")
    
    # Step 4: Display transposed format (vertical, tall)
    print("\n" + "=" * 80)
    print("TRANSPOSED FORMAT (Vertical - Tall) - RECOMMENDED")
    print("=" * 80)
    
    transposed = result['transposed_format']
    print(f"\nColumn Headers (Line Items): {', '.join(transposed['column_headers'][:5])}...")
    print(f"Row Headers (Years): {transposed['row_headers']}")
    
    # Show sample data
    print("\nSample Data (first 3 years):")
    for year in transposed['row_headers'][:3]:
        print(f"\n{year}:")
        for i, col_header in enumerate(transposed['column_headers'][:3]):
            value = transposed['data'][year].get(col_header, 'N/A')
            print(f"  {col_header}: {value}")
    
    # Step 5: Validate data integrity
    print("\n" + "=" * 80)
    print("DATA VALIDATION")
    print("=" * 80)
    
    validation = result['validation']
    print(f"\nStatus: {validation['status'].upper()}")
    print(f"Original data points: {validation['stats']['original_data_points']}")
    print(f"Transposed data points: {validation['stats']['transposed_data_points']}")
    
    if validation['errors']:
        print("\nErrors:")
        for error in validation['errors']:
            print(f"  ❌ {error}")
    
    if validation['warnings']:
        print("\nWarnings:")
        for warning in validation['warnings']:
            print(f"  ⚠️  {warning}")
    
    if validation['status'] == 'valid':
        print("\n✅ Data integrity verified - no loss or leakage!")
    
    # Step 6: Format as DataFrame
    print("\n" + "=" * 80)
    print("PANDAS DATAFRAME (Transposed)")
    print("=" * 80)
    
    df = consolidator.format_as_dataframe(result, use_transposed=True)
    print(f"\nShape: {df.shape}")
    print(f"Index (Years): {list(df.index)}")
    print(f"Columns (Line Items): {list(df.columns)[:5]}...")
    
    print("\nDataFrame Preview:")
    print(df.head())
    
    # Step 7: Format as Markdown
    print("\n" + "=" * 80)
    print("MARKDOWN TABLE")
    print("=" * 80)
    
    markdown = consolidator.format_as_markdown(result, use_transposed=True)
    print(markdown)


def example_convenience_function():
    """Example using convenience function."""
    print("\n" + "=" * 80)
    print("CONVENIENCE FUNCTION EXAMPLE")
    print("=" * 80)
    
    vs = get_unified_vectordb("chromadb")
    em = get_embedding_manager()
    
    # Query
    query_embedding = em.generate_embedding("total assets")
    search_results = vs.search(query_embedding, top_k=50)
    
    # One-line consolidation
    df = consolidate_and_transpose(
        search_results=search_results,
        table_title="Consolidated Balance Sheet",
        format='dataframe'
    )
    
    print("\nConsolidated DataFrame:")
    print(df)


def example_rag_workflow():
    """
    Example: Complete RAG workflow with consolidation.
    
    User Query: "Show me total assets from 2020 to 2024"
    """
    print("\n" + "=" * 80)
    print("COMPLETE RAG WORKFLOW")
    print("=" * 80)
    
    user_query = "Show me total assets from 2020 to 2024"
    print(f"\nUser Query: '{user_query}'")
    
    # Step 1: Semantic search
    print("\n1. Semantic search...")
    vs = get_unified_vectordb("chromadb")
    em = get_embedding_manager()
    
    query_embedding = em.generate_embedding(user_query)
    search_results = vs.search(
        query_embedding=query_embedding,
        top_k=50,
        filters={"statement_type": "balance_sheet"}
    )
    
    print(f"   Found {len(search_results)} relevant chunks")
    
    # Step 2: Consolidate tables
    print("\n2. Consolidating tables...")
    df = consolidate_and_transpose(
        search_results=search_results,
        table_title="Consolidated Balance Sheet",
        format='dataframe'
    )
    
    # Step 3: Extract answer
    print("\n3. Extracting answer...")
    
    if 'Total Assets' in df.columns:
        total_assets = df['Total Assets']
        
        print("\nAnswer:")
        print("=" * 40)
        for year, value in total_assets.items():
            print(f"{year}: {value}")
        print("=" * 40)
    else:
        print("   Total Assets not found in consolidated table")


def main():
    """Run all examples."""
    print("\n")
    print("╔" + "=" * 78 + "╗")
    print("║" + " " * 15 + "TABLE CONSOLIDATION & TRANSPOSE EXAMPLES" + " " * 23 + "║")
    print("╚" + "=" * 78 + "╝")
    
    try:
        example_consolidate_balance_sheet()
        example_convenience_function()
        example_rag_workflow()
    except Exception as e:
        print(f"\n⚠️  Note: Examples require populated VectorDB")
        print(f"   Error: {e}")
        print("\n   Run process_raw_data.py first to populate data")
    
    print("\n" + "=" * 80)
    print("EXAMPLES COMPLETE")
    print("=" * 80)
    print("\nKey Features:")
    print("1. ✅ Multi-year consolidation (2020-2024)")
    print("2. ✅ Automatic transpose (years as rows)")
    print("3. ✅ Data integrity validation (no loss/leakage)")
    print("4. ✅ Multiple output formats (DataFrame, Markdown, Dict)")
    print("\n" + "=" * 80)


if __name__ == '__main__':
    main()
