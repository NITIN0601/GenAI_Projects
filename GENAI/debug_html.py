#!/usr/bin/env python3
"""Debug PyMuPDF HTML output."""

import fitz

pdf_path = '../raw_data/10q0320.pdf'
doc = fitz.open(pdf_path)
page = doc[56]  # Page 57

# Get HTML
html = page.get_text("html")

# Save to file for inspection
with open('page57_html.html', 'w') as f:
    f.write(html)

print(f"HTML saved to page57_html.html ({len(html)} chars)")
print("\nFirst 2000 characters:")
print(html[:2000])

# Check if there are any <table> tags
if '<table' in html.lower():
    print("\n✓ Found <table> tags in HTML")
else:
    print("\n✗ No <table> tags found - PyMuPDF doesn't output tables as HTML")
    print("Need to use different extraction method")

doc.close()
