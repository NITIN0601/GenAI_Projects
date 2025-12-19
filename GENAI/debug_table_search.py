import pandas as pd
import os
import glob

files = glob.glob("/Users/nitin/Desktop/Chatbot/Morgan/GENAI/data/processed/*.xlsx")
search_title = "Difference between contractual principal and Fair value"

print(f"Searching for: {search_title}")

for file in files:
    if "~$" in file: continue
    try:
        # Read the Index sheet to find the table
        df_index = pd.read_excel(file, sheet_name="Index")
        # Match case-insensitively and partial
        matches = df_index[df_index['Table Title'].str.contains(search_title, case=False, na=False)]
        
        if not matches.empty:
            print(f"\nFile: {os.path.basename(file)}")
            for _, row in matches.iterrows():
                print(f"  - Section: {row.get('Section', 'N/A')}")
                print(f"  - Sheet: {row.get('Sheet Name', 'N/A')}")
                print(f"  - Title: {row.get('Table Title', 'N/A')}")
    except Exception as e:
        print(f"Error reading {file}: {e}")
