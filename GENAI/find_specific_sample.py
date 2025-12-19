import pandas as pd

file = "/Users/nitin/Desktop/Chatbot/Morgan/GENAI/data/extracted/consolidated_tables.xlsx"
search_text = "Difference between contractual principal and Fair value"

try:
    xl = pd.ExcelFile(file)
    for sheet in xl.sheet_names:
        if sheet == 'Index': continue
        # Read just first few rows to check title
        df = pd.read_excel(file, sheet_name=sheet, nrows=5)
        # Check if any cell in the first column contains the title
        if any(df.iloc[:, 0].astype(str).str.contains(search_text, case=False, na=False)):
            print(f"FOUND: {sheet}")
            # Output full table head
            df_full = pd.read_excel(file, sheet_name=sheet)
            print(df_full.head(15).to_markdown(index=False))
            print("---")
except Exception as e:
    print(f"Error: {e}")
