import pandas as pd

file = "/Users/nitin/Desktop/Chatbot/Morgan/GENAI/data/extracted/consolidated_tables.xlsx"
search_text = "Difference Between Contractual Principal"

try:
    xl = pd.ExcelFile(file)
    for sheet in xl.sheet_names:
        if "Financial Instruments Not Me" in sheet:
            df = pd.read_excel(file, sheet_name=sheet)
            # Look for the title in ANY cell of the first few rows
            if df.astype(str).apply(lambda x: x.str.contains(search_text, case=False)).any().any():
                print(f"### SHEET: {sheet}")
                print(df.head(15).to_markdown(index=False))
                print("\n")
except Exception as e:
    print(f"Error: {e}")
