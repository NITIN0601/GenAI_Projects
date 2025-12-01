from src.extraction.enrichment import get_metadata_enricher

def test_enrichment():
    enricher = get_metadata_enricher()
    
    # Test Case 1: Balance Sheet with Millions
    content1 = """
    | Assets | 2024 | 2023 |
    |---|---|---|
    | Cash | $ 100 | $ 90 |
    (in millions)
    """
    meta1 = enricher.enrich_table_metadata(content1, "Consolidated Balance Sheet")
    print("Test 1 (Balance Sheet/Millions):")
    print(f"  Statement Type: {meta1.get('statement_type')}")
    print(f"  Units: {meta1.get('units')}")
    print(f"  Currency: {meta1.get('currency')}")
    print(f"  Structure: {meta1.get('table_structure')}")
    
    assert meta1.get('statement_type') == 'balance_sheet'
    assert meta1.get('units') == 'millions'
    assert meta1.get('currency') == 'USD'
    
    # Test Case 2: Income Statement with Billions
    content2 = """
    | Revenue | Q1 | Q2 | Q3 | Q4 |
    |---|---|---|---|---|
    | Net Rev | 10 | 11 | 12 | 13 |
    (in billions)
    """
    meta2 = enricher.enrich_table_metadata(content2, "Statement of Income")
    print("\nTest 2 (Income/Billions/Multi-col):")
    print(f"  Statement Type: {meta2.get('statement_type')}")
    print(f"  Units: {meta2.get('units')}")
    print(f"  Structure: {meta2.get('table_structure')}")
    
    assert meta2.get('statement_type') == 'income_statement'
    assert meta2.get('units') == 'billions'
    assert meta2.get('table_structure') == 'multi_column'

    print("\n✅ All tests passed!")

if __name__ == "__main__":
    test_enrichment()
