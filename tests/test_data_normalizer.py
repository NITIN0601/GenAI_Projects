"""
Test script for Data Normalizer.

Tests the wide-to-long format transformation with various scenarios.
"""

import sys
from pathlib import Path
import pandas as pd

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.infrastructure.extraction.exporters.csv_exporter.data_normalizer import DataNormalizer
from src.utils import get_logger

logger = get_logger(__name__)


def test_simple_period_headers():
    """Test 1: Simple period headers without suffix."""
    print("\n" + "="*80)
    print("TEST 1: Simple Period Headers")
    print("="*80)
    
    # Input data
    data = {
        'Source': ['10q0925.pdf_pg7', '10q0925.pdf_pg7'],
        'Section': ['Business', 'Business'],
        'Table Title': ['Financial Info', 'Financial Info'],
        'Category': ['Results', 'Results'],
        'Product/Entity': ['Net revenues', 'ROE'],
        'Q3-QTD-2025': ['$18,224', '18.0%'],
        'Q3-QTD-2024': ['$15,000', '15.0%'],
    }
    
    df = pd.DataFrame(data)
    
    print("\nInput (Wide Format):")
    print(df.to_string(index=False))
    
    # Transform
    normalizer = DataNormalizer()
    normalized = normalizer.normalize_table(df)
    
    print("\nOutput (Long Format):")
    print(normalized.to_string(index=False))
    
    # Validate
    assert len(normalized) == 4, f"Expected 4 rows, got {len(normalized)}"
    assert 'Dates' in normalized.columns, "Missing 'Dates' column"
    assert 'Header' in normalized.columns, "Missing 'Header' column"
    assert 'Data Value' in normalized.columns, "Missing 'Data Value' column"
    assert all(normalized['Header'] == ''), "Header should be empty for simple periods"
    
    print("\n✅ Test 1 PASSED")


def test_period_with_suffix():
    """Test 2: Period headers with suffix (IS, WM, etc)."""
    print("\n" + "="*80)
    print("TEST 2: Period Headers with Suffix")
    print("="*80)
    
    # Input data
    data = {
        'Source': ['10q0925.pdf_pg7'],
        'Section': ['Business'],
        'Table Title': ['Financial Info'],
        'Category': ['Results'],
        'Product/Entity': ['Net revenues'],
        'Q3-2025 IS': ['$5,000'],
        'Q3-2025 WM': ['$3,500'],
        'Q3-2025 Total': ['$8,500'],
    }
    
    df = pd.DataFrame(data)
    
    print("\nInput (Wide Format):")
    print(df.to_string(index=False))
    
    # Transform
    normalizer = DataNormalizer()
    normalized = normalizer.normalize_table(df)
    
    print("\nOutput (Long Format):")
    print(normalized.to_string(index=False))
    
    # Validate
    assert len(normalized) == 3, f"Expected 3 rows, got {len(normalized)}"
    assert normalized.iloc[0]['Dates'] == 'Q3-2025', "Dates should be Q3-2025"
    assert normalized.iloc[0]['Header'] == 'IS', "Header should be IS"
    assert normalized.iloc[1]['Header'] == 'WM', "Header should be WM"
    assert normalized.iloc[2]['Header'] == 'Total', "Header should be Total"
    
    print("\n✅ Test 2 PASSED")


def test_mixed_period_types():
    """Test 3: Mixed period types (QTD, YTD, quarterly)."""
    print("\n" + "="*80)
    print("TEST 3: Mixed Period Types")
    print("="*80)
    
    # Input data
    data = {
        'Source': ['10q0925.pdf_pg7'],
        'Section': ['Business'],
        'Table Title': ['Financial Info'],
        'Category': ['Results'],
        'Product/Entity': ['Net revenues'],
        'Q3-QTD-2025': ['$18,224'],
        'Q3-2025': ['$6,000'],
        'YTD-2024': ['$50,000'],
        'Q3-YTD-2025 IM': ['$25,000'],
    }
    
    df = pd.DataFrame(data)
    
    print("\nInput (Wide Format):")
    print(df.to_string(index=False))
    
    # Transform
    normalizer = DataNormalizer()
    normalized = normalizer.normalize_table(df)
    
    print("\nOutput (Long Format):")
    print(normalized.to_string(index=False))
    
    # Validate
    assert len(normalized) == 4, f"Expected 4 rows, got {len(normalized)}"
    assert normalized.iloc[0]['Dates'] == 'Q3-QTD-2025', "Dates should be Q3-QTD-2025"
    assert normalized.iloc[1]['Dates'] == 'Q3-2025', "Dates should be Q3-2025"
    assert normalized.iloc[2]['Dates'] == 'YTD-2024', "Dates should be YTD-2024"
    assert normalized.iloc[3]['Dates'] == 'Q3-YTD-2025', "Dates should be Q3-YTD-2025"
    assert normalized.iloc[3]['Header'] == 'IM', "Header should be IM"
    
    print("\n✅ Test 3 PASSED")


def test_unit_indicators_excluded():
    """Test 4: Unit indicator columns are excluded."""
    print("\n" + "="*80)
    print("TEST 4: Unit Indicator Exclusion")
    print("="*80)
    
    # Input data
    data = {
        'Source': ['10q0925.pdf_pg7'],
        'Section': ['Business'],
        'Table Title': ['Financial Info'],
        'Category': ['Results'],
        'Product/Entity': ['Net revenues'],
        '$ in millions': ['Currency'],
        'Q3-QTD-2025': ['18,224'],
        'Q3-QTD-2024': ['15,000'],
    }
    
    df = pd.DataFrame(data)
    
    print("\nInput (Wide Format):")
    print(df.to_string(index=False))
    
    # Transform
    normalizer = DataNormalizer()
    normalized = normalizer.normalize_table(df)
    
    print("\nOutput (Long Format):")
    print(normalized.to_string(index=False))
    
    # Validate - should only have 2 rows (2 period columns)
    assert len(normalized) == 2, f"Expected 2 rows, got {len(normalized)}"
    assert '$ in millions' not in normalized.columns, "Unit indicator should be excluded"
    
    print("\n✅ Test 4 PASSED")


def test_row_count_expansion():
    """Test 5: Row count expansion (N rows × M periods = N*M rows)."""
    print("\n" + "="*80)
    print("TEST 5: Row Count Expansion")
    print("="*80)
    
    # Input data - 3 rows × 4 period columns = 12 output rows
    data = {
        'Source': ['10q0925.pdf_pg7'] * 3,
        'Section': ['Business'] * 3,
        'Table Title': ['Financial Info'] * 3,
        'Category': ['Results'] * 3,
        'Product/Entity': ['Net revenues', 'ROE', 'Net income'],
        'Q1-2025': ['$1,000', '10%', '$500'],
        'Q2-2025': ['$2,000', '12%', '$600'],
        'Q3-2025': ['$3,000', '15%', '$700'],
        'Q4-2025': ['$4,000', '18%', '$800'],
    }
    
    df = pd.DataFrame(data)
    
    print("\nInput (Wide Format):")
    print(df.to_string(index=False))
    print(f"\nInput: {len(df)} rows × 4 period columns")
    
    # Transform
    normalizer = DataNormalizer()
    normalized = normalizer.normalize_table(df)
    
    print("\nOutput (Long Format) - First 10 rows:")
    print(normalized.head(10).to_string(index=False))
    print(f"\nOutput: {len(normalized)} rows (expected: {len(df) * 4})")
    
    # Validate
    expected_rows = len(df) * 4
    assert len(normalized) == expected_rows, f"Expected {expected_rows} rows, got {len(normalized)}"
    
    print("\n✅ Test 5 PASSED")


def test_non_period_headers():
    """Test 6: Non-period headers (MS/PF, Total, % change)."""
    print("\n" + "="*80)
    print("TEST 6: Non-Period Headers")
    print("="*80)
    
    # Input data
    data = {
        'Source': ['10q0925.pdf_pg7'],
        'Section': ['Business'],
        'Table Title': ['Financial Info'],
        'Category': ['Results'],
        'Product/Entity': ['Net revenues'],
        'MS/PF': ['Mixed'],
        'Total': ['$10,000'],
        '% change': ['5%'],
    }
    
    df = pd.DataFrame(data)
    
    print("\nInput (Wide Format):")
    print(df.to_string(index=False))
    
    # Transform
    normalizer = DataNormalizer()
    normalized = normalizer.normalize_table(df)
    
    print("\nOutput (Long Format):")
    print(normalized.to_string(index=False))
    
    # Validate - non-period headers should go to Dates column
    assert len(normalized) == 3, f"Expected 3 rows, got {len(normalized)}"
    assert normalized.iloc[0]['Dates'] == 'MS/PF', "Non-period header should be in Dates"
    assert all(normalized['Header'] == ''), "Header should be empty for non-period headers"
    
    print("\n✅ Test 6 PASSED")


def test_empty_values():
    """Test 7: Empty cell values are preserved."""
    print("\n" + "="*80)
    print("TEST 7: Empty Values Preserved")
    print("="*80)
    
    # Input data with empty values
    data = {
        'Source': ['10q0925.pdf_pg7'],
        'Section': ['Business'],
        'Table Title': ['Financial Info'],
        'Category': ['Results'],
        'Product/Entity': ['Net revenues'],
        'Q3-2025': ['$5,000'],
        'Q4-2025': [''],  # Empty value
        'Q1-2026': ['-'],  # Dash
    }
    
    df = pd.DataFrame(data)
    
    print("\nInput (Wide Format):")
    print(df.to_string(index=False))
    
    # Transform
    normalizer = DataNormalizer()
    normalized = normalizer.normalize_table(df)
    
    print("\nOutput (Long Format):")
    print(normalized.to_string(index=False))
    
    # Validate
    assert len(normalized) == 3, f"Expected 3 rows, got {len(normalized)}"
    assert normalized.iloc[1]['Data Value'] == '', "Empty value should be preserved"
    assert normalized.iloc[2]['Data Value'] == '-', "Dash should be preserved"
    
    print("\n✅ Test 7 PASSED")


def main():
    """Run all tests."""
    print("\n" + "="*80)
    print("DATA NORMALIZER TEST SUITE")
    print("="*80)
    
    try:
        test_simple_period_headers()
        test_period_with_suffix()
        test_mixed_period_types()
        test_unit_indicators_excluded()
        test_row_count_expansion()
        test_non_period_headers()
        test_empty_values()
        
        print("\n" + "="*80)
        print("✅ ALL TESTS PASSED")
        print("="*80 + "\n")
        
    except AssertionError as e:
        print("\n" + "="*80)
        print(f"❌ TEST FAILED: {e}")
        print("="*80 + "\n")
        sys.exit(1)
    except Exception as e:
        print("\n" + "="*80)
        print(f"❌ ERROR: {e}")
        print("="*80 + "\n")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
