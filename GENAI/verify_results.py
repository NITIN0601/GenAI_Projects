import pandas as pd
import os

file = "/Users/nitin/Desktop/Chatbot/Morgan/GENAI/data/extracted/consolidated_tables.xlsx"
search_title = "Difference between contractual principal and Fair value"

print(f"Checking results in: {file}")

try:
    df_index = pd.read_excel(file, sheet_name="Index")
    matches = df_index[df_index['Table Title'].str.contains(search_title, case=False, na=False)]
    
    if not matches.empty:
        print(f"\nFound {len(matches)} entries for this table:")
        # Sort by link/sheet to see if Structure suffix was used
        for _, row in matches.iterrows():
            print(f"  - Sheet: {row.get('Link', 'N/A')}")
            print(f"  - Title: {row.get('Table Title', 'N/A')}")
            print(f"  - Sources: {row.get('Sources', 'N/A')}")
    else:
        print("\nTable not found in Index!")
except Exception as e:
    print(f"Error: {e}")
