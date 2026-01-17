"""
Simple test script for Category Separator (no pytest required).
"""

import sys
sys.path.insert(0, '.')

import pandas as pd
from src.infrastructure.extraction.exporters.csv_exporter.category_separator import CategorySeparator


def test_simple_category_extraction():
    """Test simple category extraction."""
    print("\n=== Test 1: Simple Category Extraction ===")
    
    separator = CategorySeparator()
    
    data = [
        ['$ in millions', 'Q3-QTD-2025', 'Q3-QTD-2024', 'Q3-YTD-2025', 'Q3-YTD-2024'],
        ['', '', '', '', ''],
        ['Consolidated results', '', '', '', ''],
        ['Net revenues', 18224, 15383, 52755, 45538],
        ['Consolidated financial measures', '', '', '', ''],
        ['ROE', 0.18, 0.131, 0.165, 0.135],
        ['Pre-tax margin by segment', '', '', '', ''],
        ['Institutional Securities', 0.37, 0.28, 0.34, 0.3],
    ]
    
    df = pd.DataFrame(data)
    result_df, categories = separator.separate_categories(df)
    
    print(f"Categories found: {categories}")
    print(f"\nResult DataFrame ({len(result_df)} rows):")
    print(result_df.to_string())
    
    assert len(categories) == 3
    assert 'Consolidated results' in categories
    assert len(result_df) == 3
    print("✓ Test 1 PASSED")


def test_no_categories():
    """Test table with no categories."""
    print("\n=== Test 2: No Categories Present ===")
    
    separator = CategorySeparator()
    
    data = [
        ['$ in millions', 'Q3-2025', 'Q3-2024'],
        ['Net revenues', 18224, 15383],
        ['Compensation expense', 7442, 6733],
    ]
    
    df = pd.DataFrame(data)
    result_df, categories = separator.separate_categories(df)
    
    print(f"Categories found: {categories}")
    print(f"\nResult DataFrame ({len(result_df)} rows):")
    print(result_df.to_string())
    
    assert len(categories) == 0
    assert all(result_df['Category'] == '')
    assert len(result_df) == 2
    print("✓ Test 2 PASSED")


def test_repeated_header_text():
    """Test repeated header text pattern."""
    print("\n=== Test 3: Repeated Header Text Pattern ===")
    
    separator = CategorySeparator()
    
    data = [
        ['$ in millions', 'Q3-2025', 'Q3-2024'],
        ['', '', ''],
        ['State and municipal securities', 'State and municipal securities', 'State and municipal securities'],
        ['Beginning balance', 10, 34],
        ['Ending balance', 13, 13],
    ]
    
    df = pd.DataFrame(data)
    result_df, categories = separator.separate_categories(df)
    
    print(f"Categories found: {categories}")
    print(f"\nResult DataFrame ({len(result_df)} rows):")
    print(result_df.to_string())
    
    assert len(categories) == 1
    assert 'State and municipal securities' in categories
    assert len(result_df) == 2
    print("✓ Test 3 PASSED")


def test_dash_values():
    """Test handling of dash values."""
    print("\n=== Test 4: Dash Values ===")
    
    separator = CategorySeparator()
    
    data = [
        ['$ in millions', 'Q3-2025', 'Q3-2024'],
        ['Category A', '', ''],
        ['Item with dashes', '$-', '-'],
        ['Regular item', 100, 90],
    ]
    
    df = pd.DataFrame(data)
    result_df, categories = separator.separate_categories(df)
    
    print(f"Categories found: {categories}")
    print(f"\nResult DataFrame ({len(result_df)} rows):")
    print(result_df.to_string())
    
    # Dash rows are DATA, not categories
    assert len(categories) == 1  # Only 'Category A'
    assert 'Category A' in categories
    assert len(result_df) == 2  # Both data rows included
    
    # Check dash values preserved
    dash_row = result_df[result_df['Product/Entity'] == 'Item with dashes'].iloc[0]
    assert dash_row['Q3-2025'] == '$-'
    assert dash_row['Q3-2024'] == '-'
    
    print("✓ Test 4 PASSED")


def main():
    """Run all tests."""
    print("=" * 60)
    print("Category Separator Test Suite")
    print("=" * 60)
    
    try:
        test_simple_category_extraction()
        test_no_categories()
        test_repeated_header_text()
        test_dash_values()
        
        print("\n" + "=" * 60)
        print("✓ ALL TESTS PASSED")
        print("=" * 60)
        
    except AssertionError as e:
        print(f"\n✗ TEST FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
