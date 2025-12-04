import sys
import os
sys.path.append(os.getcwd())

from src.extraction.consolidation.table_consolidator import get_multi_year_consolidator
import pandas as pd

def test_consolidation():
    print("Testing MultiYearTableConsolidator...")
    
    # Mock search results
    search_results = [
        {
            "content": "| Item | Value |\n|---|---|\n| Revenue | $100 |\n| Cost | $50 |",
            "metadata": {"table_title": "Financials", "year": 2020, "quarter": "Q4"}
        },
        {
            "content": "| Item | Value |\n|---|---|\n| Revenue | $120 |\n| Cost | $60 |",
            "metadata": {"table_title": "Financials", "year": 2021, "quarter": "Q4"}
        },
        {
            # Test different format (colon separated)
            "content": "Revenue: $150\nCost: $70",
            "metadata": {"table_title": "Financials", "year": 2022, "quarter": "Q4"}
        }
    ]
    
    consolidator = get_multi_year_consolidator()
    result = consolidator.consolidate_multi_year_tables(search_results, "Financials")
    
    if "error" in result:
        print(f"FAILED: {result['error']}")
        return

    print("\nConsolidated Data (Transposed):")
    df = pd.DataFrame(result['transposed_format']['data']).T
    print(df)
    
    # Validation
    years = result['years']
    if years != [2020, 2021, 2022]:
        print(f"FAILED: Expected years [2020, 2021, 2022], got {years}")
        return
        
    print("\nSUCCESS: Consolidation verified.")

if __name__ == "__main__":
    test_consolidation()
