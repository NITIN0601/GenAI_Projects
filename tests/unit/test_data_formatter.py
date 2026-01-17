"""
Quick manual test for data formatter.

Tests all edge cases outlined in the data formatting plan.
"""

import pandas as pd
from src.infrastructure.extraction.exporters.csv_exporter.data_formatter import (
    DataFormatter,
    format_currency,
    format_percentage,
    detect_table_format,
    detect_column_format,
    detect_row_format
)


def test_currency_formatting():
    """Test currency formatting edge cases."""
    print("\n=== Currency Formatting ===")
    
    test_cases = [
        (18224, "$18,224"),
        (-248, "($248)"),
        (-22865, "($22,865)"),
        ("$ (717)", "($717)"),
        ("$ (2,173)", "($2,173)"),
        (2.8, "$2.80"),
        ("$-", "-"),
        ("$ -", "-"),
        ("N/M", "N/M"),
    ]
    
    for value, expected in test_cases:
        result = format_currency(value)
        status = "✅" if result == expected else "❌"
        print(f"{status} {value!r:20} → {result:20} (expected: {expected})")


def test_percentage_formatting():
    """Test percentage formatting edge cases."""
    print("\n=== Percentage Formatting ===")
    
    test_cases = [
        ("17.4 %", "17.4%"),
        ("(5)%", "-5.0%"),
        (0.18, "18.0%"),
        (0.67, "67.0%"),
        ("1% to 4% (3%)", "1% to 4% (3%)"),
        ("99.7%", "99.7%"),
        ("-", "-"),
    ]
    
    for value, expected in test_cases:
        result = format_percentage(value)
        status = "✅" if result == expected else "❌"
        print(f"{status} {value!r:30} → {result:30} (expected: {expected})")


def test_detection():
    """Test format detection."""
    print("\n=== Format Detection ===")
    
    # Table format detection
    print("\nTable Format Detection:")
    table_headers = [
        ("$ in millions", {'type': 'currency', 'unit': 'millions', 'has_exceptions': False}),
        ("$ in billions", {'type': 'currency', 'unit': 'billions', 'has_exceptions': False}),
        ("$ in millions, except per share data", {'type': 'currency', 'unit': 'millions', 'has_exceptions': True}),
    ]
    
    for header, expected in table_headers:
        result = detect_table_format(header)
        status = "✅" if result == expected else "❌"
        print(f"{status} '{header}' → {result}")
    
    # Row format detection
    print("\nRow Format Detection:")
    row_labels = [
        ("ROE", "percentage"),
        ("Expense efficiency ratio", "percentage"),
        ("Pre-tax margin", "percentage"),
        ("Net revenues", "currency"),
    ]
    
    for label, expected in row_labels:
        result = detect_row_format(label)
        status = "✅" if result == expected else "❌"
        print(f"{status} '{label}' → {result}")


def test_full_table_formatting():
    """Test full table formatting with DataFrame."""
    print("\n=== Full Table Formatting ===")
    
    # Create test DataFrame
    data = {
        'Category': ['Assets', 'Assets', 'Metrics', 'Metrics'],
        'Product/Entity': ['Cash', 'Loans', 'ROE', 'Net revenues'],
        'Q3-2025': [18224, -248, 0.18, 2666],
        'Q2-2025': ['$ (717)', 15383, '17.4 %', '$ (2,173)'],
        '% change': [5.2, -13.5, 'N/M', '-']
    }
    
    df = pd.DataFrame(data)
    
    print("\nOriginal DataFrame:")
    print(df.to_string())
    
    formatter = DataFormatter()
    formatted_df = formatter.format_table(df, table_header='$ in millions')
    
    print("\nFormatted DataFrame:")
    print(formatted_df.to_string())
    
    # Verify specific cells
    print("\n\nKey Cell Checks:")
    checks = [
        ("Cash, Q3-2025", formatted_df.loc[0, 'Q3-2025'], "$18,224"),
        ("Loans, Q3-2025", formatted_df.loc[1, 'Q3-2025'], "($248)"),
        ("ROE, Q3-2025", formatted_df.loc[2, 'Q3-2025'], "18.0%"),
        ("Cash, Q2-2025", formatted_df.loc[0, 'Q2-2025'], "($717)"),
        ("ROE, Q2-2025", formatted_df.loc[2, 'Q2-2025'], "17.4%"),
        ("Cash, % change", formatted_df.loc[0, '% change'], "5.2%"),
    ]
    
    for label, result, expected in checks:
        status = "✅" if str(result) == expected else "❌"
        print(f"{status} {label}: {result!r} (expected: {expected!r})")


if __name__ == "__main__":
    print("=" * 70)
    print("DATA FORMATTER TEST SUITE")
    print("=" * 70)
    
    test_currency_formatting()
    test_percentage_formatting()
    test_detection()
    test_full_table_formatting()
    
    print("\n" + "=" * 70)
    print("Tests complete!")
    print("=" * 70)
