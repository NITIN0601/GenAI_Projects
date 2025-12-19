import sys
import os
sys.path.append(os.getcwd())

from src.infrastructure.extraction.formatters.table_formatter import TableStructureFormatter

def test_title_stripping():
    # Case 1: Title row is present and matches title
    title = "Business Unit Responsible for Risk Management"
    markdown = """
| Business Unit Responsible for Risk Management | | |
|---|---|---|
| Institutional Securities | $100 | $200 |
| Wealth Management | $50 | $60 |
"""
    print(f"Testing with title: '{title}'")
    parsed = TableStructureFormatter.parse_markdown_table(markdown, title=title)
    
    headers = parsed.get('columns', [])
    rows = parsed.get('rows', [])
    
    print("Parsed Headers:", headers)
    print("Parsed First Row:", rows[0] if rows else "No rows")
    
    # Expectation: 
    # The first row "Business Unit..." should be removed from headers.
    # The headers should actually be empty or derived from the separator context if it was weird.
    # Wait, in the example above, I made "Business Unit..." the first row.
    # If the separator is there, "Business Unit..." is before separator -> Header.
    # If I designate it as title, it should be removed.
    # Then headers will be empty? Or should we have column headers?
    # In my fix: if header_lines is empty after removal, I didn't verify what happens if there are no other header lines.
    # But usually there IS a header line.
    
    # Let's try a case where the title is inserted erroneously BEFORE the real header
    markdown_with_real_header = """
| Business Unit Responsible for Risk Management | | |
| Metric | 2023 | 2024 |
|---|---|---|
| Institutional Securities | $100 | $200 |
"""
    print("\nTesting with title row + real header row:")
    parsed = TableStructureFormatter.parse_markdown_table(markdown_with_real_header, title=title)
    headers = parsed.get('columns', [])
    print("Parsed Headers:", headers)
    
    if headers == ['Metric', '2023', '2024']:
        print("PASS: Title row removed, real header preserved.")
    else:
        print("FAIL: Headers mismatch.")

    # Case 2: No separator, title is first line
    markdown_no_sep = """
| Business Unit Responsible for Risk Management | | |
| Metric | 2023 | 2024 |
| Institutional Securities | $100 | $200 |
"""
    print("\nTesting with NO separator, title row + real header row:")
    parsed = TableStructureFormatter.parse_markdown_table(markdown_no_sep, title=title)
    headers = parsed.get('columns', [])
    rows = parsed.get('rows', [])
    print("Parsed Headers:", headers)
    print("First Data Row:", rows[0] if rows else "No rows")

    # In no-sep logic:
    # Sep index = -1.
    # Loop:
    # Line 0 (Title): -> header_lines (since empty)
    # Line 1 (Metric): -> data_lines (since header_lines not empty)
    # Post-processing:
    # Check header_lines[0] (Title) vs Title. Match! -> Pop it.
    # header_lines is empty.
    # data_lines starts with Metric.
    # My fix: if not header_lines and data_lines and sep == -1: -> promote data_lines[0] to header.
    # So 'Metric' row becomes header.
    
    if headers == ['Metric', '2023', '2024']:
        print("PASS: Title row removed, next row promoted to header.")
    else:
        print(f"FAIL: Expected ['Metric', '2023', '2024'], got {headers}")

if __name__ == "__main__":
    test_title_stripping()
